"""Open mic, wake phrase, then a short window for one command."""

import json
import logging
import math
import queue
from collections import deque
import threading
import time
import winsound
from array import array
from pathlib import Path

import sounddevice as sd
from PySide6.QtCore import QObject, Signal
from vosk import KaldiRecognizer, Model, SetLogLevel

from app.bag import Bag, spoken_phrases
from app.focus import prepare_gspro
from app.commands import (
    CLOSABLE,
    COMMANDS,
    STOPPABLE,
    WAKE_PHRASES,
    contains_wake,
    is_continue,
    key_label,
    match_command,
    hold_key,
    holds_key,
    press_keys,
    press_times,
    release_key,
    repeat_count,
    spoken_text,
)
from app.paths import resource_path
from app.prefs_page import Tuning, load_tuning

log = logging.getLogger(__name__)

SAMPLE_RATE = 16000
MODEL_NAME = "vosk-model-small-en-us-0.15"


def model_path() -> Path:
    return resource_path("models", MODEL_NAME)


def input_devices() -> list[tuple[int, str]]:
    """One entry per mic. DirectSound keeps the full device name and opens reliably."""
    devices = list(enumerate(sd.query_devices()))
    inputs = [(index, dev) for index, dev in devices if int(dev["max_input_channels"]) > 0]

    def host_name(dev: dict) -> str:
        return str(sd.query_hostapis(int(dev["hostapi"]))["name"])

    def real(items: list[tuple[int, dict]]) -> list[tuple[int, dict]]:
        skipped = ("mapper", "primary sound")
        picked = [item for item in items if not any(word in item[1]["name"].lower() for word in skipped)]
        return picked or items

    for label in ("DirectSound", "MME", "WASAPI"):
        group = real([item for item in inputs if label.upper() in host_name(item[1]).upper()])
        if group:
            return [(index, str(dev["name"])) for index, dev in group]
    return [(index, str(dev["name"])) for index, dev in inputs]


def default_input_index() -> int | None:
    default = sd.default.device[0]
    try:
        index = int(default)
    except (TypeError, ValueError):
        return None
    return index if index >= 0 else None


class VoiceListener(QObject):
    """One audio thread lists devices and owns the microphone.

    PortAudio (WASAPI in particular) misbehaves if the UI thread initializes
    it and a worker thread then starts the stream.
    """

    level = Signal(int)
    decibels = Signal(float)  # real-scale dB, or nan while the input is under the gate
    calibrated = Signal(float)  # new offset from dBFS to real-scale dB
    status = Signal(str)
    heard = Signal(str)
    command = Signal(str)
    notice = Signal(str)
    club = Signal(str)
    mics = Signal(object)
    transcript = Signal(str, float, float)  # text, average dB, peak dB of the voiced audio (nan if none)

    def __init__(self, spl_offset: float = 0.0, tuning: Tuning | None = None) -> None:
        super().__init__()
        self.bag = Bag()
        self.tuning = tuning or load_tuning()
        self.send_keys = True
        # Added to dBFS to get real-scale dB (see calibrate()).
        self.spl_offset = spl_offset
        self._recent: deque = deque(maxlen=2000)  # (time, dBFS) of recent blocks
        self._commands: queue.Queue = queue.Queue()
        self._thread = threading.Thread(target=self._thread_main, name="gspraudio-mic", daemon=True)
        self._started = False

    def start(self) -> None:
        if not self._started:
            self._started = True
            self._thread.start()

    def use_device(self, device: int) -> None:
        self._commands.put(("device", int(device)))

    def use_player(self) -> None:
        self.bag.reload()
        self._commands.put(("player", None))

    def _spl(self, dbfs: float) -> float:
        """A dBFS reading on the calibrated scale (the same dB people know from a sound meter)."""
        return dbfs + self.spl_offset

    def use_page(self, title: str) -> None:
        self._commands.put(("page", title))

    def calibrate(self, baseline_db: float) -> None:
        """Measure the room for a few seconds and set the offset so it reads baseline_db."""
        self._commands.put(("calibrate", float(baseline_db)))

    def shutdown(self) -> None:
        self._commands.put(("quit", None))
        if self._thread.is_alive() and threading.current_thread() is not self._thread:
            self._thread.join(timeout=2)

    def _thread_main(self) -> None:
        try:
            devices = input_devices()
            preferred = default_input_index()
        except Exception as exc:
            log.exception("device list failed")
            self.status.emit(f"Microphone failed: {exc}")
            return
        self.mics.emit((devices, preferred))
        if not devices:
            self.status.emit("No microphone found")

        path = model_path()
        if not path.is_dir():
            self.status.emit(f"Missing speech model: {path}")
            return
        self.status.emit("Loading speech model…")
        SetLogLevel(-1)
        try:
            model = Model(str(path))
            # One grammar for the wake words and the commands. A separate wake
            # grammar turns the command into [unk] before the command listener
            # ever sees it, unless the result is exactly "hey caddy".
            rec = KaldiRecognizer(
                model,
                SAMPLE_RATE,
                _grammar(WAKE_PHRASES + tuple(COMMANDS) + spoken_phrases()),
            )
        except Exception as exc:
            log.exception("model load failed")
            self.status.emit(f"Speech model failed: {exc}")
            return

        audio_q: queue.Queue[bytes] = queue.Queue()
        accept = True

        def on_audio(indata, frames, time_info, status) -> None:
            if accept:
                audio_q.put(bytes(indata))

        stream = None
        rate = SAMPLE_RATE
        armed_until = 0.0
        last_partial = ""
        last_close: tuple[str, str | tuple[str, ...]] | None = None
        open_stops: dict[str, str | tuple[str, ...]] = {}
        holding: str | None = None
        down = False
        hold_next = 0.0
        # Mic setup page: same grammar as the commands, so the transcript shows what commands would hear.
        # Voice page: the command recognizer runs. Any other page: neither.
        capture_rec = None
        capture_db: list[float] = []  # dB of each voiced block since the last utterance
        voice_on = True

        def idle_status() -> None:
            if holding or open_stops:
                self.status.emit('Say "hey caddy stop"')
            else:
                self.status.emit('Say "hey caddie"')

        def release() -> None:
            nonlocal holding, down
            if holding and down:
                release_key(holding)
            holding = None
            down = False

        def switch(device: int) -> None:
            nonlocal stream, rate, armed_until, last_partial
            _close_stream(stream)
            stream = None
            _drain(audio_q)
            armed_until = 0.0
            last_partial = ""
            release()
            rec.Reset()
            if capture_rec is not None:
                capture_rec.Reset()
            try:
                rate, stream = _open_stream(device, on_audio)
            except Exception as exc:
                log.exception("mic open failed")
                stream = None
                self.status.emit(f"Microphone failed: {exc}")
                return
            log.info("mic open device=%s rate=%s", device, rate)
            idle_status()

        def handle(data: bytes) -> None:
            nonlocal armed_until, last_partial, last_close, open_stops, holding, down, hold_next

            def toggle_stop(name: str, keys: str | tuple[str, ...]) -> None:
                if name not in STOPPABLE:
                    return
                if name in open_stops:
                    del open_stops[name]
                else:
                    open_stops[name] = keys
            db = _db(data)
            now = time.time()
            self._recent.append((now, db))
            while self._recent and now - self._recent[0][0] > self.tuning.calibrate_seconds * 3:
                self._recent.popleft()
            self.level.emit(_percent(db, self.tuning.gate_db, self.tuning.full_scale_db))
            # Calibrated dB, shown as-is even when quieter than the baseline. Only digital silence is withheld.
            self.decibels.emit(self._spl(db) if db > SILENT_DB else float("nan"))
            pcm = data if rate == SAMPLE_RATE else _to_16k(data, rate)
            if not pcm:
                return
            if capture_rec is not None:
                capture_db.append(db)
                if capture_rec.AcceptWaveform(pcm):
                    said = describe_heard(json.loads(capture_rec.Result()).get("text", "").strip())
                    voiced = [level for level in capture_db if level >= self.tuning.gate_db]
                    avg = self._spl(sum(voiced) / len(voiced)) if voiced else float("nan")
                    peak = self._spl(max(capture_db)) if capture_db else float("nan")
                    capture_db.clear()
                    if said:
                        self.transcript.emit(said, avg, peak)
                return
            if not voice_on:
                return
            if rec.AcceptWaveform(pcm):
                raw = json.loads(rec.Result()).get("text", "").strip()
                text = spoken_text(raw)
                last_partial = ""
                log.info("heard %s", raw)
                if not text or text == "hey":
                    return
                self.heard.emit(text)
                phrase = match_command(text)
                if phrase and (contains_wake(text) or armed_until):
                    armed_until = 0.0
                    note = ""
                    if phrase not in ("close", "stop") and not is_continue(phrase) and not holds_key(phrase):
                        release()
                    if phrase == "stop":
                        move = None
                        had_hold = holding is not None
                        pending = dict(open_stops)
                        if not had_hold and not pending:
                            label = "—"
                            sent = False
                            note = "Nothing to stop"
                        else:
                            release()
                            label = "stopped"
                            sent = had_hold
                            if pending and self.send_keys:
                                note = prepare_gspro() or ""
                                if not note:
                                    for name, keys in pending.items():
                                        press_keys(keys)
                                        open_stops.pop(name, None)
                                    if last_close is not None and last_close[0] in pending:
                                        last_close = None
                                    sent = True
                            elif pending and not had_hold:
                                sent = False
                    elif phrase == "close":
                        move = None
                        release()
                        if last_close is None:
                            label = "—"
                            sent = False
                            note = "Nothing to close"
                        else:
                            label, binding = last_close
                            sent = self.send_keys
                            if sent:
                                note = prepare_gspro() or ""
                                if note:
                                    sent = False
                                else:
                                    press_keys(binding)
                                    toggle_stop(label, binding)
                    else:
                        move = self.bag.apply(phrase)
                    if phrase in ("close", "stop"):
                        pass
                    elif move is not None:
                        self.club.emit(self.bag.club)
                        label = move.detail
                        sent = bool(move.keys) and self.send_keys
                        if sent:
                            note = prepare_gspro() or ""
                            if note:
                                sent = False
                            else:
                                press_times(move.keys)
                    else:
                        binding = COMMANDS[phrase]
                        if (is_continue(phrase) or holds_key(phrase)) and isinstance(binding, str):
                            label = (
                                f"{key_label(binding)} continue"
                                if is_continue(phrase)
                                else key_label(binding)
                            )
                            sent = self.send_keys
                            if sent:
                                note = prepare_gspro() or ""
                                if note:
                                    sent = False
                                else:
                                    keep_down = holds_key(phrase)
                                    if keep_down:
                                        if holding != binding or not down:
                                            release()
                                            hold_key(binding)
                                            holding = binding
                                            down = True
                                    else:
                                        if holding and down:
                                            release_key(holding)
                                        holding = binding
                                        down = False
                                        hold_next = time.time()
                            else:
                                release()
                        else:
                            count = repeat_count(phrase)
                            label = key_label(binding)
                            if count > 1:
                                label = f"{label} x{count}"
                            sent = self.send_keys
                            if sent:
                                note = prepare_gspro() or ""
                                if note:
                                    sent = False
                                else:
                                    if isinstance(binding, str) and count > 1:
                                        press_times([binding] * count)
                                    else:
                                        press_keys(binding)
                        if phrase in CLOSABLE:
                            last_close = (phrase, binding)
                        if sent:
                            toggle_stop(phrase, binding)
                    _beep(1200, 80)
                    held = move is not None and not move.keys
                    if not sent and not held and not note:
                        note = "not sent"
                    self.command.emit(f"{phrase} → {label}")
                    self.notice.emit(note)
                    idle_status()
                elif contains_wake(text):
                    armed_until = time.time() + self.tuning.command_window_seconds
                    _beep(800, 80)
                    self.status.emit("Listening for a command")
            else:
                partial = spoken_text(json.loads(rec.PartialResult()).get("partial", ""))
                if not partial or partial == last_partial or partial == "hey":
                    return
                last_partial = partial
                self.heard.emit(partial)

        try:
            while True:
                if armed_until and time.time() >= armed_until:
                    armed_until = 0.0
                    idle_status()
                if holding and not self.send_keys:
                    release()
                    idle_status()
                if holding and not down and time.time() >= hold_next:
                    hold_next = time.time() + 0.12
                    if self.send_keys:
                        press_keys(holding)
                try:
                    command = self._commands.get(timeout=0.05)
                except queue.Empty:
                    command = None
                if command is not None:
                    kind, value = command
                    if kind == "quit":
                        return
                    if kind == "device":
                        switch(value)
                        continue
                    if kind == "calibrate":
                        cutoff = time.time() - self.tuning.calibrate_seconds
                        levels = [db for when, db in self._recent if when >= cutoff and db > SILENT_DB]
                        if levels:
                            self.spl_offset = value - sum(levels) / len(levels)
                            self.calibrated.emit(self.spl_offset)
                            self.status.emit(f"Calibrated: room noise set to {value:.0f} dB")
                        else:
                            self.status.emit("No audio to calibrate from")
                        continue
                    if kind == "page":
                        listening = value == "Voice"
                        capturing = value == "Mic setup"
                        if voice_on and not listening:
                            release()
                            armed_until = 0.0
                        if listening and not voice_on:
                            rec.Reset()
                            armed_until = 0.0
                            idle_status()
                        voice_on = listening
                        if capturing and capture_rec is None:
                            capture_rec = KaldiRecognizer(
                                model,
                                SAMPLE_RATE,
                                _grammar(WAKE_PHRASES + tuple(COMMANDS) + spoken_phrases() + (UNKNOWN_TOKEN,)),
                            )
                            capture_db.clear()
                        elif not capturing:
                            capture_rec = None
                        continue
                    if kind == "player":
                        release()
                        armed_until = 0.0
                        rec = KaldiRecognizer(
                            model,
                            SAMPLE_RATE,
                            _grammar(WAKE_PHRASES + tuple(COMMANDS) + spoken_phrases()),
                        )
                        idle_status()
                        continue
                while True:
                    try:
                        handle(audio_q.get_nowait())
                    except queue.Empty:
                        break
        finally:
            accept = False
            release()
            _close_stream(stream)


def _open_stream(device: int, callback):
    native = int(sd.query_devices(device, "input")["default_samplerate"])
    rates: list[int] = []
    for rate in (SAMPLE_RATE, native):
        if rate > 0 and rate not in rates:
            rates.append(rate)
    error: Exception | None = None
    for rate in rates:
        stream = None
        try:
            stream = sd.RawInputStream(callback=callback, **_stream_args(device, rate))
            stream.start()
            return rate, stream
        except sd.PortAudioError as exc:
            error = exc
            log.info("mic rate %s rejected for device %s: %s", rate, device, exc)
            _close_stream(stream)
    assert error is not None
    raise error


def _close_stream(stream) -> None:
    if stream is None:
        return
    try:
        stream.stop()
    finally:
        stream.close()


def _drain(audio_q: queue.Queue) -> None:
    while True:
        try:
            audio_q.get_nowait()
        except queue.Empty:
            return


def _stream_args(device: int | None, rate: int) -> dict:
    args: dict = {
        "samplerate": rate,
        "blocksize": 0,
        "dtype": "int16",
        "channels": 1,
        "device": device,
    }
    if device is None:
        return args
    host = sd.query_hostapis(int(sd.query_devices(device)["hostapi"]))
    if "WASAPI" in str(host["name"]).upper():
        args["extra_settings"] = sd.WasapiSettings(exclusive=False)
    return args


def _to_16k(data: bytes, source_rate: int) -> bytes:
    src = array("h")
    src.frombytes(data)
    if len(src) < 2:
        return b""
    out_len = int(len(src) * SAMPLE_RATE / source_rate)
    dst = array("h", [0] * out_len)
    step = source_rate / SAMPLE_RATE
    pos = 0.0
    last = len(src) - 1
    for index in range(out_len):
        left = int(pos)
        if left >= last:
            dst[index] = src[last]
        else:
            frac = pos - left
            mixed = src[left] * (1.0 - frac) + src[left + 1] * frac
            dst[index] = int(mixed)
        pos += step
    return dst.tobytes()


UNKNOWN_TOKEN = "[unk]"
UNKNOWN_TEXT = "(I have no idea what that was, but I heard it)"


def describe_heard(raw: str) -> str:
    """Turn a raw recognizer result into a line for the Mic setup page."""
    tokens = raw.split()
    if not tokens:
        return ""
    if all(token == UNKNOWN_TOKEN for token in tokens):
        return UNKNOWN_TEXT
    return " ".join("(unknown)" if token == UNKNOWN_TOKEN else token for token in tokens)


def _grammar(phrases: tuple[str, ...]) -> str:
    return json.dumps(list(phrases))


SILENT_DB = -120.0


def _db(data: bytes) -> float:
    """Loudness of one audio block in dB relative to full scale (0 dB = loudest)."""
    samples = array("h")
    samples.frombytes(data)
    if not samples:
        return SILENT_DB
    total = sum(sample * sample for sample in samples)
    rms = (total / len(samples)) ** 0.5
    if rms <= 0:
        return SILENT_DB
    return 20 * math.log10(rms / 32768)


# Below the gate the mic is only hiss, so the page shows "silent" and an empty bar.
# The top is where the bar reads full. Adjust both once real speech numbers are in.
def _percent(db: float, gate_db: float, full_scale_db: float) -> int:
    if db < gate_db:
        return 0
    span = full_scale_db - gate_db
    return max(0, min(100, int((db - gate_db) / span * 100)))


def _beep(freq: int, ms: int) -> None:
    try:
        winsound.Beep(freq, ms)
    except RuntimeError:
        log.info("beep unavailable")
