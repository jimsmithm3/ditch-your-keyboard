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

from app import course_chooser, text_entry
from app import shadows
from app.bag import Bag, spoken_phrases
from app.gspro_courses import course_phrases
from app.gspro_screens import (
    group_grammar,
    GROUP_GRAMMAR_NAMES,
    PANEL_GROUP_NAMES,
    RECORDS_BY_KEY,
    SCREEN_GROUP_NAMES,
    grammar_groups_for,
    panel_group,
    DIALOG_GROUP,
    DIALOG_PHRASES,
    GRID_GROUP,
    GRID_INDEX,
    GRID_PHRASES,
    recognizer_setup,
    screen_group,
)
from app.gspro_tree import SYNC_PHRASES
from app.focus import ensure_gspro, prepare_gspro
from app.debug_press import debug_press_in_background
from app.gspro_sequences import (
    COURSE_LIST_SCREENS,
    ROUND_SETTINGS_SCREENS,
    current_panel,
    SEQUENCES,
    current_screen,
    run_course_in_background,
    MAP_SIZE_PHRASES,
    set_map_size,
    toggle_map,
    sync_screen,
    run_in_background as run_gspro_sequence,
    confirm_exit,
    request_exit,
    set_ui_hidden,
    ui_hidden,
    MARKER_DIRECTIONS,
    FLIGHT_TOGGLE_PHRASES,
    MAP_MODE_PHRASES,
    flight_mode_toggle,
    marker_active,
    marker_move,
    HOLE_NUMBER,
    HOLE_PANEL,
    cancel_hole,
    marker_cancel,
    open_hole_panel,
    pick_hole,
    marker_map_key,
    marker_end,
    marker_placing,
    place_marker,
    marker_stop,
    motion_active,
    SLIDER_PHRASES,
    close_wind,
    open_wind,
    slider_start,
    stop_motion,
)
from app.gspro_grid import is_showing as grid_showing
from app.launch import start_play_golf
from app.commands import (
    CLOSABLE,
    COMMANDS,
    STOPPABLE,
    LAUNCH_PHRASE,
    DEBUG_PHRASE,
    COURSE_PHRASE,
    parse_course,
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
from app.prefs import get_pref
from app.prefs_page import Tuning, load_tuning
from app.grammar_words import NAV, TOGGLE

log = logging.getLogger(__name__)

VOICE_PAGES = ("Voice", "Overview")  # pages where voice commands run
WAKE_REQUIRED_KEY = "wake_required"  # "True" = say "hey caddie" first; "False" = a command is heard alone
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


def _saved_mic_index(devices: list[tuple[int, str]]) -> int | None:
    """Device indexes change when hardware is plugged or unplugged, so the mic is saved by name."""
    from app.prefs import get_pref

    saved = get_pref("mic_name", "")
    for index, name in devices:
        if saved and name == saved:
            return index
    return None


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
    utterance = Signal(str)  # a finished phrase from the Voice page, before it is matched to a command
    command = Signal(str)
    notice = Signal(str)
    mode = Signal(bool)  # True when listening, False after f"{TOGGLE} listening" pauses
    available = Signal(str)  # the commands dialog: "open", "close", "current" (tab), or "always" (tab)
    grid = Signal(object)  # the numbered grid: ("show", None), ("close", None), or ("pick", digit)
    legend = Signal(object)  # the course filter's letter list: (shown, typed); drawn on the GUI thread
    grammars = Signal(object)  # the grammars listening right now, as a list of readable names (debug box)
    club = Signal(str)
    mics = Signal(object)
    transcript = Signal(str, float, float)  # text, average dB, peak dB of the voiced audio (nan if none)

    def __init__(self, spl_offset: float = 0.0, tuning: Tuning | None = None) -> None:
        super().__init__()
        self.bag = Bag()
        self.tuning = tuning or load_tuning()
        self.send_keys = True
        self.listening = True  # False after f"{TOGGLE} listening" pauses: only f"{TOGGLE} listening" is heard
        self._course_grammar_on = False  # the course-name grammar is listened for only on On course practice
        self._screen_groups_on: set[str] = set()  # the per-screen grammars switched on right now
        self._dialog_open = False  # the commands dialog is up, so its tab phrases listen
        self._grid_on = False  # the numbered grid is up, so its digit words listen
        # Added to dBFS to get real-scale dB (see calibrate()).
        self.spl_offset = spl_offset
        self._recent: deque = deque(maxlen=2000)  # (time, dBFS) of recent blocks
        self._commands: queue.Queue = queue.Queue()
        self._thread = threading.Thread(target=self._thread_main, name="ditch-your-keyboard-mic", daemon=True)
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

    def use_courses(self) -> None:
        """Rebuild the recognizer so course names added by a download are heard. Safe to call from any thread."""
        self._commands.put(("courses", None))

    def _spl(self, dbfs: float) -> float:
        """A dBFS reading on the calibrated scale (the same dB people know from a sound meter)."""
        return dbfs + self.spl_offset

    def _set_listening(self, on: bool) -> None:
        self.listening = on
        log.info("voice commands %s", "on" if on else "paused")
        self.mode.emit(on)
        self.notice.emit("Listening" if on else f"Paused. Say {TOGGLE} listening to resume.")

    def _sync_course_grammar(self, rec) -> None:
        """Listen for course names on the course list screens, and on round settings: "play <course>"
        there presses PLAY for the course already set up, and it needs the name to be heard."""
        screen = current_screen()
        want = screen in COURSE_LIST_SCREENS or screen in ROUND_SETTINGS_SCREENS
        if want == self._course_grammar_on:
            return
        self._course_grammar_on = want
        if hasattr(rec, "set_group"):  # Vosk has no groups; it listens for all words at once
            rec.set_group("courses", want)
        self._emit_grammars()

    def _emit_grammars(self) -> None:
        """Tell the debug box which grammars are listening, by readable name."""
        from app.gspro_screens import grammar_name, set_active_groups

        groups = set(self._screen_groups_on)
        if self._course_grammar_on:
            groups.add("courses")
        set_active_groups(groups)
        names = ["Always on (global)"] + sorted(grammar_name(group) for group in groups)
        self.grammars.emit(names)

    def _sync_screen_grammar(self, rec) -> None:
        """Listen for a screen's own phrases only while GSPro is on that screen. If the screen is
        not known, all the screen grammars are on, as before. If GSPro is closed, none are."""
        if not hasattr(rec, "set_group"):  # Vosk has no groups; it listens for all words at once
            return
        screen = current_screen()
        panel = current_panel()
        if panel is not None:
            wanted = {panel_group(panel)}  # an open panel replaces its screen's grammar until it closes
        elif screen is None:
            wanted = set(SCREEN_GROUP_NAMES) | set(GROUP_GRAMMAR_NAMES)
        elif screen in RECORDS_BY_KEY:
            wanted = {screen_group(screen)} | grammar_groups_for(screen)
        else:
            wanted = set()
        if self._dialog_open:
            wanted = wanted | {DIALOG_GROUP}  # the commands dialog's tab phrases, while it is open
        if text_entry.active():
            if screen is not None and screen != "on_course":
                text_entry.stop()  # the filter belongs to the course chooser; leaving it turns it off
                self.legend.emit((False, ""))
            else:
                wanted = wanted | {group_grammar("Filter entry")}  # the letters and characters, while the filter is typing
        if screen != "on_course":
            course_chooser.forget_panel()  # the course notes panel belongs to the course list
        elif course_chooser.panel_open():
            wanted = wanted | {group_grammar("Course notes panel")}  # cancel, close, read more, while it is open
        if self._grid_on and grid_showing():
            wanted = {GRID_GROUP}  # while the grid is showing, only its digit words listen, so club words cannot compete
        if wanted == self._screen_groups_on:
            return
        every_group = set(SCREEN_GROUP_NAMES) | set(PANEL_GROUP_NAMES) | set(GROUP_GRAMMAR_NAMES)
        for name in every_group | self._screen_groups_on | wanted:
            if (name in wanted) != (name in self._screen_groups_on):
                rec.set_group(name, name in wanted)
        self._screen_groups_on = wanted
        self._emit_grammars()

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
            preferred = _saved_mic_index(devices)
            if preferred is None:
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
            rec = _build_recognizer(model)
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
        # Off by default: a command is heard on its own. Turn on for noisy rooms (see Preferences).
        wake_required = get_pref(WAKE_REQUIRED_KEY, "False") == "True"

        def idle_status() -> None:
            if wake_required:
                if holding or open_stops:
                    self.status.emit('Say "hey caddy stop"')
                else:
                    self.status.emit('Say "hey caddie"')
            elif holding or open_stops:
                self.status.emit('Say "stop"')
            else:
                self.status.emit("Say a command")

        def release() -> None:
            nonlocal holding, down
            if holding and down:
                # The key-up must reach GSPro, or GSPro keeps the key down.
                note = ensure_gspro()
                if note:
                    log.warning("key-up for %s not sent: %s", holding, note)
                else:
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
                        log.info("heard (capture) %s | avg %.1f dB | peak %.1f dB", said, avg, peak)
                        self.transcript.emit(said, avg, peak)
                return
            if not voice_on:
                return
            self._sync_course_grammar(rec)
            self._sync_screen_grammar(rec)
            if rec.AcceptWaveform(pcm):
                raw = json.loads(rec.Result()).get("text", "").strip()
                text = spoken_text(raw)
                last_partial = ""
                log.info("heard %s", raw)
                if not text or text == "hey":
                    return
                self.heard.emit(text)
                self.utterance.emit(text)
                phrase = match_command(text)
                if phrase == f"{TOGGLE} listening":
                    self._set_listening(not self.listening)  # paused: this resumes; listening: this pauses
                    return
                if not self.listening:
                    return  # paused: only f"{TOGGLE} listening" gets through
                if phrase and (not wake_required or contains_wake(text) or armed_until):
                    armed_until = 0.0
                    note = ""
                    if self._grid_on and phrase not in GRID_PHRASES and phrase != "hide place":
                        # Any other command ends the grid, so the screen's own grammar can come back.
                        self._grid_on = False
                        self.grid.emit(("close", None))
                    if phrase not in ("close", "stop") and not is_continue(phrase) and not holds_key(phrase):
                        release()
                    if phrase == "stop" and not motion_active():
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
                    elif phrase == "change wind":
                        move = None
                        sent = False
                        release()
                        label = "wind"
                        note = open_wind()
                    elif phrase == "stop" or phrase in MARKER_DIRECTIONS or phrase in MAP_MODE_PHRASES or phrase in FLIGHT_TOGGLE_PHRASES or phrase in SLIDER_PHRASES:
                        # "stop" ends a marker or slider drag that is moving; the other phrases start one.
                        move = None
                        sent = False
                        label = "marker"
                        if phrase == "stop":
                            note = stop_motion()
                        elif phrase in SLIDER_PHRASES:
                            note = slider_start(phrase)
                        elif phrase in FLIGHT_TOGGLE_PHRASES:
                            note = flight_mode_toggle()
                        else:
                            note = marker_move(phrase)
                    elif phrase == "place marker":
                        move = None
                        sent = False
                        release()
                        label = "marker"
                        note = marker_end() if marker_placing() else place_marker()
                    elif phrase == "change hole":
                        move = None
                        sent = False
                        release()
                        label = "hole"
                        note = open_hole_panel()
                    elif current_panel() == HOLE_PANEL and phrase in HOLE_NUMBER:
                        move = None
                        sent = False
                        release()
                        label = "hole"
                        note = pick_hole(HOLE_NUMBER[phrase])
                    elif phrase == "cancel" and current_panel() == HOLE_PANEL:
                        move = None
                        sent = False
                        release()
                        label = "hole"
                        note = cancel_hole()
                    elif phrase == f"{TOGGLE} map" and current_panel() == "marker_panel":
                        # S only: the app's map flag is not changed, so the user can sync it afterwards.
                        move = None
                        sent = False
                        release()
                        label = "marker"
                        note = marker_map_key()
                    elif phrase == "cancel marker" and current_panel() == "marker_panel":
                        # Releases the button where the marker is, makes the map small again if place marker made it large,
                        # and leaves the marker panel.
                        move = None
                        sent = False
                        release()
                        label = "marker"
                        note = marker_cancel()
                    elif phrase in ("place ball", "place pin"):
                        move = None
                        sent = False
                        flag = phrase == "place pin"
                        label = "flag" if flag else "ball"
                        self._grid_on = True  # the grid's words listen while it is up
                        self.grid.emit(("place", "flag" if flag else "ball"))
                        note = f"Place {label}: click the {label} icon, then pick the point"
                    elif phrase == "hide place":
                        move = None
                        sent = False
                        label = "grid"
                        self._grid_on = False
                        self.grid.emit(("close", None))
                        note = "Grid closed"
                    elif phrase == "cancel place":
                        move = None
                        sent = False
                        label = "grid"
                        self._grid_on = False
                        self.grid.emit(("cancel", None))
                        note = "Grid cancelled"
                    elif (
                        phrase in course_chooser.PHRASES
                        or (course_chooser.panel_open() and phrase in course_chooser.PANEL_PHRASES)
                        or (text_entry.active() and text_entry.accepts(phrase))
                    ):
                        # The course filter: its typing and the download-by-number commands (app/course_chooser.py).
                        move = None
                        sent = False
                        release()
                        label = phrase
                        note = course_chooser.handle(phrase)
                        self.legend.emit((text_entry.active(), text_entry.typed()))
                    elif self._grid_on and phrase == "toggle map":
                        move = None
                        sent = False
                        label = "grid"
                        self.grid.emit(("map", None))
                        note = "Place: map size key pressed; flag unchanged"
                    elif self._grid_on and phrase == "redo":
                        move = None
                        sent = False
                        label = "grid"
                        self.grid.emit(("redo", None))
                        note = "Grid: redo"
                    elif self._grid_on and phrase in GRID_PHRASES:
                        move = None
                        sent = False
                        label = "grid"
                        self.grid.emit(("pick", GRID_INDEX[phrase]))
                        note = f"Grid: {phrase}"
                    elif phrase in ("open commands", "close commands"):
                        move = None
                        sent = False
                        label = "dialog"
                        self._dialog_open = phrase == "open commands"
                        self.available.emit("open" if self._dialog_open else "close")
                        note = "Showing the commands" if self._dialog_open else "Commands closed"
                    elif phrase in DIALOG_PHRASES:
                        move = None
                        sent = False
                        label = "dialog"
                        self.available.emit("current" if phrase == "show current grammar" else "always")
                        note = "Showing " + ("the current grammar" if phrase == "show current grammar" else "the always-on commands")
                    elif phrase == "close" and current_panel() == "wind_panel":
                        move = None
                        sent = False
                        release()
                        label = "wind"
                        note = close_wind()
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
                    elif phrase == LAUNCH_PHRASE:
                        move = None
                        sent = False  # no keys are sent; the note says what happened
                        release()
                        label = f"{NAV} gspro"
                        note = start_play_golf(on_done=self.notice.emit)
                    elif phrase == "play course":
                        # On round settings, the course is already set up: press its PLAY. No name is needed.
                        move = None
                        sent = False
                        release()
                        label = "play course"
                        note = run_course_in_background("", on_done=self.notice.emit)
                    elif phrase.startswith(COURSE_PHRASE) and phrase not in SEQUENCES:  # "click play" is a sequence
                        move = None
                        sent = False
                        release()
                        label = "play"
                        course, then_now = parse_course(text)
                        note = run_course_in_background(course, on_done=self.notice.emit, then_now=then_now)
                    elif phrase in SYNC_PHRASES:
                        # Tells the app which screen GSPro is on. No clicks, no keys.
                        move = None
                        sent = False
                        release()
                        label = phrase
                        note = sync_screen(SYNC_PHRASES[phrase])
                    elif phrase in MAP_SIZE_PHRASES:
                        # Tells the app the mini map's size. No clicks, no keys.
                        move = None
                        sent = False
                        release()
                        label = phrase
                        set_map_size(phrase)
                        note = "Mini map set to " + ("large" if MAP_SIZE_PHRASES[phrase] else "small")
                    elif phrase in ("gspro exit", "confirm exit"):
                        # Closing GSPro takes two steps: gspro exit, then confirm exit.
                        move = None
                        sent = False
                        release()
                        label = phrase
                        if phrase == "gspro exit":
                            note = request_exit(on_done=self.notice.emit)
                        else:
                            note = confirm_exit(on_done=self.notice.emit)
                    elif phrase in SEQUENCES:
                        # GSPro menu sequences: clicks happen in GSPro's window, not as keys.
                        move = None
                        sent = False
                        release()
                        label = phrase
                        note = run_gspro_sequence(phrase, on_done=self.notice.emit)
                    elif phrase == DEBUG_PHRASE:
                        move = None
                        sent = False
                        release()
                        label = "debug press"
                        note = debug_press_in_background(on_done=self.notice.emit)
                    else:
                        move = self.bag.apply(phrase) or shadows.apply(phrase)
                    if phrase in ("close", "stop", LAUNCH_PHRASE, DEBUG_PHRASE) or phrase.startswith(COURSE_PHRASE) or phrase in SEQUENCES or phrase in SYNC_PHRASES or phrase in MAP_SIZE_PHRASES or phrase == "confirm exit" or phrase in MARKER_DIRECTIONS or phrase in MAP_MODE_PHRASES or phrase in FLIGHT_TOGGLE_PHRASES or phrase in SLIDER_PHRASES or phrase in ("open commands", "close commands") or phrase in DIALOG_PHRASES or phrase in ("hide place", "place ball", "place pin") or phrase in course_chooser.PHRASES or (text_entry.active() and text_entry.accepts(phrase)) or (self._grid_on and phrase in GRID_PHRASES):
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
                        if phrase == f"{TOGGLE} ui":
                            # One phrase for both: Esc shows the interface again, H hides it.
                            binding = "esc" if ui_hidden() else "h"
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
                            # Esc (show ui, open menu) always leaves the interface showing.
                            if phrase == f"{TOGGLE} ui":
                                set_ui_hidden(binding == "h")
                            elif binding == "esc":
                                set_ui_hidden(False)
                            if binding == "s":
                                toggle_map()  # S expands or shrinks the mini map
                    _beep(1200, 80)
                    held = move is not None and not move.keys
                    if not sent and not held and not note:
                        note = "not sent"
                    self.command.emit(f"{phrase} → {label}")
                    self.notice.emit(note)
                    idle_status()
                elif wake_required and contains_wake(text):
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
                        note = ensure_gspro()
                        if note:
                            # GSPro lost the front and could not be brought back. Stop the repeat.
                            release()
                            self.notice.emit(note)
                            idle_status()
                        else:
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
                        listening = value in VOICE_PAGES
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
                                _grammar(WAKE_PHRASES + tuple(COMMANDS) + spoken_phrases() + course_phrases() + (UNKNOWN_TOKEN,)),
                            )
                            capture_db.clear()
                        elif not capturing:
                            capture_rec = None
                        continue
                    if kind in ("player", "courses"):
                        release()
                        armed_until = 0.0
                        _close_recognizer(rec)
                        rec = _build_recognizer(model)
                        self._course_grammar_on = False  # the new recognizer starts with the course grammar off
                        self._screen_groups_on = set()  # and with every screen grammar off
                        if kind == "courses":
                            self.legend.emit((False, ""))  # a download finished: the letter list goes away
                        idle_status()
                        continue
                while True:
                    try:
                        handle(audio_q.get_nowait())
                    except queue.Empty:
                        break
                    except Exception:
                        # One bad phrase must not stop the listener thread for good.
                        log.exception("voice handling failed; listening continues")
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


RECOGNIZER_KEY = "recognizer"  # "wsapi" (Windows speech, default) or "vosk"


EXIT_PHRASES = ("confirm exit",)  # the second step; only heard when the Confirm Exit preference is on


def _build_recognizer(model):
    """The command recognizer: always-listening phrases, the course names, and one grammar per screen."""
    from app.prefs import get_pref

    always, screen_grammars = recognizer_setup(tuple(spoken_phrases()))
    if get_pref("confirm_exit", "False") != "True":
        always = tuple(p for p in always if p not in EXIT_PHRASES)
        screen_grammars = {key: tuple(p for p in phrases if p not in EXIT_PHRASES) for key, phrases in screen_grammars.items()}
    groups = {"courses": course_phrases(), DIALOG_GROUP: DIALOG_PHRASES, GRID_GROUP: GRID_PHRASES, **screen_grammars}
    return _new_recognizer(model, WAKE_PHRASES + always, groups)


def _new_recognizer(model, phrases: tuple[str, ...], groups: dict[str, tuple[str, ...]] | None = None):
    """Windows speech when chosen and it starts. Otherwise Vosk, so voice control still works.
    Groups are listened for only when switched on. Vosk cannot switch them, so it gets them all."""
    from app.prefs import get_pref

    if get_pref(RECOGNIZER_KEY, "wsapi") == "wsapi":
        try:
            from app.wsapi_recognizer import WsapiRecognizer

            return WsapiRecognizer(phrases, groups)
        except Exception:
            log.exception("windows speech failed to start, using Vosk")
    everything = tuple(phrases) + tuple(p for group in (groups or {}).values() for p in group)
    return KaldiRecognizer(model, SAMPLE_RATE, _grammar(everything))


def _close_recognizer(rec) -> None:
    close = getattr(rec, "close", None)
    if close is not None:
        close()


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
