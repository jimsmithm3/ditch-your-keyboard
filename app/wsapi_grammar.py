"""Build a Windows speech (SRGS) grammar from a phrase list.

Windows speech recognition loads grammars as XML (W3C SRGS). Every phrase is one
<item> in a single <one-of>, so the recognizer can only return a phrase from the list.
"""

import sys
from xml.sax.saxutils import escape

GRAMMAR_NS = "http://www.w3.org/2001/06/grammar"


def normalize(phrase: str) -> str:
    return " ".join(phrase.lower().split())


def phrases_to_srgs(phrases) -> str:
    """Return the grammar as an XML string. Duplicates and empty phrases are dropped."""
    seen: set[str] = set()
    items: list[str] = []
    for phrase in phrases:
        text = normalize(phrase)
        if not text or text in seen:
            continue
        seen.add(text)
        items.append(f"      <item>{escape(text)}</item>")
    if not items:
        raise ValueError("no phrases to build a grammar from")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<grammar version="1.0" xml:lang="en-US" mode="voice" root="cmd" xmlns="{GRAMMAR_NS}">\n'
        '  <rule id="cmd" scope="public">\n'
        "    <one-of>\n"
        + "\n".join(items)
        + "\n    </one-of>\n"
        "  </rule>\n"
        "</grammar>\n"
    )


def all_phrases() -> tuple[str, ...]:
    """Wake phrases, command phrases, and the active player's club phrases and nicknames."""
    from app.bag import spoken_phrases
    from app.commands import COMMANDS, WAKE_PHRASES

    return tuple(WAKE_PHRASES) + tuple(COMMANDS) + tuple(spoken_phrases())


if __name__ == "__main__":
    # --out writes UTF-8 directly. Shell redirects (PowerShell's >) write UTF-16, which the grammar loader rejects.
    xml = phrases_to_srgs(all_phrases())
    if len(sys.argv) == 3 and sys.argv[1] == "--out":
        from pathlib import Path

        Path(sys.argv[2]).write_text(xml, encoding="utf-8")
        print(f"wrote {sys.argv[2]}")
    else:
        sys.stdout.write(xml)
