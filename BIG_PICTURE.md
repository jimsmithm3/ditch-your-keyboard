# Ditch Your Keyboard: big picture

Living notes. Add to it as decisions get made. Keep it short. Details live in `HANDOFF.md`.

## Why it exists

Golf sim at home. GSPro is projected onto a wall, so the player is standing and swinging in front of it. A keyboard or clicker breaks the immersion. ditch-your-keyboard listens for voice commands ("aim left five", "hey caddie stop") and sends the matching keystrokes to GSPro, so the player never touches a device.

## Setup

- GSPro runs full screen on its own monitor (monitor 1, LG 4K, 125% scaling). It's shown on a projector onto the wall.
- Dev monitor (monitor 2) is the work screen, with the taskbar on both monitors.
- GSPro has no API for most actions, so keystrokes are the interface.

## Principles

- Keys go to the focused window, so focus GSPro once per command and don't re-focus between keys.
- Only offer voice commands for keys that are wired and working. Unwired commands stay in the table, greyed out.
- Immersion first. If something needs a click or a look at the screen, it's a candidate for voice, not a reason to leave the game.
- Two ways a command fires. (1) Start phrase: "hey caddie" opens a 5-second window (screen flashes green), and a command said in that window fires. (2) Bare command: the command said alone fires without a start phrase. In both cases the parser list (grammar) decides what counts as a command. A command buried in ordinary talk does nothing.

## Decisions

- First pass: practice in a quiet room, just the player and the golf balls. Voice is the target, so the first pass is about making the key commands and voice matching work well in that setting.
- Party mode (louder rooms, more people) is a later option. It may need a stronger recognizer. Vosk, Windows speech, or VoiceAttack all stay open until then.
- Windows-only is fine, since GSPro is Windows-only.
- Recognizer: when the rewrite happens, switch from Vosk to the Windows speech API (the DLL route), and start with bare commands only (no start phrase). The start phrase is a later addition, and it's a small if/else on top of the same grammar, so it can be added then without a redesign.
- Before the switch is final, the check that matters is whether bare commands fire reliably in the practice room with the Windows recognizer.
- The demo that inspired this appears to have used a live mic with a limited set of words, not full speech-to-text. The bare-command rule comes from that.

## Status

- Priority now: make the GSPro key commands solid (aim, club, map, view, close, continue).
- Later: "play match" by clicking a fixed spot in GSPro's window. Plan is in `HANDOFF.md`.
- Not started: anything beyond the key commands.

## Open questions

- Does GSPro expose its play-match button to accessibility tools? That would make the click more reliable than fixed coordinates.

## Log

- Display: switched monitor 2 from duplicate to extend, which fixed the second monitor showing as a tiny box.
- Page rule: voice commands run only while the Voice page is open. Words are captured only while the Mic setup page is open. Other pages do neither. The mic itself stays open while the app runs, and the level bar lives on Mic setup.
- Added a "Preferences" page. It saves the baseline room noise (default 30 dB) and has a Calibrate button. Calibrate measures the room for 3 seconds and sets an offset so the room reads the baseline. The offset is saved, and the mic page and transcript then show real-scale dB. Sound-meter reference: quiet room about 30 dB, normal conversation about 55–65 dB, shouting about 80–90 dB, measured at about a meter.
- Preferences is now the MCT Constants table, ported in. Rows: baseline room noise, noise gate, level full scale, calibrate seconds, command window, and send keys at start. Most apply after a restart. Plan: purge unused rows later.
- Added a "Mic setup" page. It holds the mic chooser, a recognizer radio (Vosk in use, Windows speech API greyed out until built), and a test that shows what's heard in a rolling text box. Test mode ignores commands, so it never sends keys to GSPro.
- Dropdown shows one GSPro display entry because both monitors are the same model. GSPro launches on monitor 1 by selecting it.
