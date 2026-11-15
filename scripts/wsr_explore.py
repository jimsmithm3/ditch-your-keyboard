"""Explore what Windows speech recognition (System.Speech) does with the ditch-your-keyboard grammar.

Usage (from the project folder):
    .\\.venv\\Scripts\\python.exe scripts\\wsr_explore.py 30
    .\\.venv\\Scripts\\python.exe scripts\\wsr_explore.py 30 --dictation

It listens on the default Windows input for the number of seconds given and prints:
  * every accepted phrase with confidence and the next-best alternates
  * every rejected utterance with its best guess and confidence
  * the timeout settings the engine is using

--dictation swaps the command grammar for free dictation, to see how it hears
speech that is not in the list.
"""

import sys
import tempfile
import time
from pathlib import Path

import clr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SPEECH_DLL = r"C:\Windows\Microsoft.NET\assembly\GAC_MSIL\System.Speech\v4.0_4.0.0.0__31bf3856ad364e35\System.Speech.dll"
clr.AddReference(SPEECH_DLL)

from System import EventHandler  # noqa: E402
from System.Globalization import CultureInfo  # noqa: E402
from System.Speech.Recognition import (  # noqa: E402
    DictationGrammar,
    Grammar,
    RecognizeMode,
    SpeechRecognitionEngine,
    SpeechRecognitionRejectedEventArgs,
    SpeechRecognizedEventArgs,
)

from app.wsapi_grammar import all_phrases, phrases_to_srgs  # noqa: E402


def alternates_text(result, limit: int = 3) -> str:
    items = []
    for alt in list(result.Alternates)[1 : limit + 1]:
        items.append(f"{alt.Text} ({alt.Confidence:.2f})")
    return ", ".join(items) if items else "-"


def main() -> None:
    seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 30.0
    dictation = "--dictation" in sys.argv

    engine = SpeechRecognitionEngine(CultureInfo("en-US"))
    try:
        if dictation:
            engine.LoadGrammar(DictationGrammar())
            mode = "dictation"
        else:
            grammar_file = Path(tempfile.gettempdir()) / "ditch-your-keyboard_commands.srgs.xml"
            grammar_file.write_text(phrases_to_srgs(all_phrases()), encoding="utf-8")
            engine.LoadGrammar(Grammar(str(grammar_file)))
            mode = f"command grammar ({len(all_phrases())} phrases)"
        engine.SetInputToDefaultAudioDevice()

        print(f"mode: {mode}")
        print(f"recognizer: {engine.RecognizerInfo.Name}")
        print(
            "timeouts: initial silence "
            f"{engine.InitialSilenceTimeout.TotalSeconds:.1f}s, babble "
            f"{engine.BabbleTimeout.TotalSeconds:.1f}s, end silence "
            f"{engine.EndSilenceTimeout.TotalSeconds:.2f}s, end silence (ambiguous) "
            f"{engine.EndSilenceTimeoutAmbiguous.TotalSeconds:.2f}s"
        )
        print(f"listening for {seconds:.0f}s...\n")

        def on_recognized(sender, event: SpeechRecognizedEventArgs) -> None:
            result = event.Result
            print(
                f"ACCEPT  {result.Text!r:28} conf {result.Confidence:.2f}   "
                f"next: {alternates_text(result)}"
            )

        def on_rejected(sender, event: SpeechRecognitionRejectedEventArgs) -> None:
            result = event.Result
            guess = result.Text if result and result.Text else "(nothing)"
            conf = result.Confidence if result else 0.0
            print(f"REJECT  best guess {guess!r:24} conf {conf:.2f}")

        engine.SpeechRecognized += EventHandler[SpeechRecognizedEventArgs](on_recognized)
        engine.SpeechRecognitionRejected += EventHandler[SpeechRecognitionRejectedEventArgs](on_rejected)
        engine.RecognizeAsync(RecognizeMode.Multiple)

        end = time.time() + seconds
        while time.time() < end:
            time.sleep(0.05)
        engine.RecognizeAsyncStop()
        print("\ndone")
    finally:
        engine.Dispose()


if __name__ == "__main__":
    main()
