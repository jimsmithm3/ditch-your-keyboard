"""Windows speech recognition: the command recognizer the listener uses.

listener.py calls AcceptWaveform, Result, PartialResult and Reset. This class
answers them.

Windows speech listens on the Windows default recording device by itself. The
mic chooser and the level meter still use our own stream, but the words come
from the default device. Set the default recording device in Windows Sound
settings to the microphone you want.

Results arrive on Windows speech's own thread and are queued. AcceptWaveform
is called from the listener thread once per audio block.
"""

import json
import logging
import os
import queue
import tempfile
import threading

import clr

from app.wsapi_grammar import phrases_to_srgs

log = logging.getLogger(__name__)

SPEECH_DLL = (
    r"C:\Windows\Microsoft.NET\assembly\GAC_MSIL\System.Speech\v4.0_4.0.0.0__31bf3856ad364e35"
    r"\System.Speech.dll"
)
clr.AddReference(SPEECH_DLL)

from System import EventHandler  # noqa: E402
from System.Globalization import CultureInfo  # noqa: E402
from System.Speech.Recognition import (  # noqa: E402
    Grammar,
    RecognizeMode,
    SpeechHypothesizedEventArgs,
    SpeechRecognitionEngine,
    SpeechRecognitionRejectedEventArgs,
    SpeechRecognizedEventArgs,
)


class WsapiRecognizer:
    """Drop-in for the parts of KaldiRecognizer that listener.py uses."""

    def __init__(self, phrases, groups: dict[str, tuple[str, ...]] | None = None) -> None:
        """phrases is always listening. Each group is its own grammar, loaded now and turned on
        or off with set_group(), so a screen can listen for its own words only."""
        self._queue: queue.Queue = queue.Queue()
        self._lock = threading.Lock()
        self._partial = ""
        self._current: str | None = None  # finished utterance waiting for Result()
        self._engine = SpeechRecognitionEngine(CultureInfo("en-US"))
        self._groups: dict[str, Grammar] = {}
        self._load("main", phrases, enabled=True)
        for name, group in (groups or {}).items():
            if group:
                self._load(name, group, enabled=False)

        self._engine.SetInputToDefaultAudioDevice()
        self._on_recognized = EventHandler[SpeechRecognizedEventArgs](self._recognized)
        self._on_hypothesized = EventHandler[SpeechHypothesizedEventArgs](self._hypothesized)
        self._on_rejected = EventHandler[SpeechRecognitionRejectedEventArgs](self._rejected)
        self._engine.SpeechRecognized += self._on_recognized
        self._engine.SpeechHypothesized += self._on_hypothesized
        self._engine.SpeechRecognitionRejected += self._on_rejected
        self._engine.RecognizeAsync(RecognizeMode.Multiple)
        log.info("windows speech started: %s", self._engine.RecognizerInfo.Name)

    def _load(self, name: str, phrases, enabled: bool) -> None:
        fd, path = tempfile.mkstemp(prefix="ditch-your-keyboard_", suffix=".srgs.xml")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(phrases_to_srgs(phrases))
            grammar = Grammar(path)
        finally:
            os.remove(path)  # the grammar is read when it is loaded, so the file is no longer needed
        grammar.Name = name
        grammar.Enabled = enabled
        self._engine.LoadGrammar(grammar)
        self._groups[name] = grammar

    def set_group(self, name: str, enabled: bool) -> None:
        """Turn a grammar group on or off. Cheap: no reload."""
        grammar = self._groups.get(name)
        if grammar is not None:
            grammar.Enabled = enabled
            log.info("speech group %s %s", name, "on" if enabled else "off")

    # Windows speech thread
    def _rejected(self, sender, event) -> None:
        """Speech the engine heard but did not match to a phrase. Logged so a missed word can be seen."""
        words = ""
        try:
            words = " ".join(str(w.Text) for w in event.Result.Words)
        except Exception:
            pass
        log.info("wsapi rejected speech: %r (%.2f)", words or "?", float(event.Result.Confidence))

    def _recognized(self, sender, event) -> None:
        text = str(event.Result.Text).strip().lower()
        log.info("wsapi heard %s (%.2f)", text, float(event.Result.Confidence))
        with self._lock:
            self._partial = ""
        self._queue.put(text)

    def _hypothesized(self, sender, event) -> None:
        with self._lock:
            self._partial = str(event.Result.Text).strip().lower()

    # Listener thread, same calls as KaldiRecognizer
    def AcceptWaveform(self, pcm: bytes) -> bool:
        """The audio is not used here, because Windows speech reads the device itself.
        Returns True when a finished utterance is ready for Result()."""
        if self._current is None:
            try:
                self._current = self._queue.get_nowait()
            except queue.Empty:
                return False
        return True

    def Result(self) -> str:
        text, self._current = self._current or "", None
        return json.dumps({"text": text})

    def PartialResult(self) -> str:
        with self._lock:
            return json.dumps({"partial": self._partial})

    def Reset(self) -> None:
        self._current = None
        with self._lock:
            self._partial = ""
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                return

    def close(self) -> None:
        try:
            self._engine.RecognizeAsyncCancel()
        finally:
            self._engine.Dispose()
