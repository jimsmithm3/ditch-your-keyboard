# Ditch Your Keyboard: big picture

Living notes. Add to it as decisions get made. Keep it short. Details live in `HANDOFF.md`. The plug-in design lives in `docs/ARCHITECTURE.md`.

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
- Two ways a command fires. (1) Start phrase: "hey caddie" opens a 5-second window (screen flashes green), and a command said in that window fires. (2) Bare command: the command said alone fires. The Preferences switch "Wake Phrase Required" (`wake_required`) picks between them. It is off by default, so bare commands are the default. The grammar decides what counts as a command. A command buried in ordinary talk does nothing.

## Decisions

- First pass: practice in a quiet room, just the player and the golf balls. Voice is the target, so the first pass is about making the key commands and voice matching work well in that setting.
- Party mode (louder rooms, more people) is a later option. It may need a stronger recognizer. Windows speech or VoiceAttack stay open until then.
- Windows-only is fine, since GSPro is Windows-only.
- Recognizer: Windows speech API only. Vosk was removed on 2026-11-15.
- Bare commands are the default. The start phrase is an option on the Preferences page, so it can be turned on for noisy rooms.
- Before the switch is final, the check that matters is whether bare commands fire reliably in the practice room with the Windows recognizer.
- One base app, with one game plug-in active at a time. GSPro is the first plug-in and Pure Play is planned. The base app will ask each plug-in to handle a phrase, so one game's phrases never listen alongside another's. The choice is made on the overview page's Game dropdown and takes effect after a restart. Full design: `docs/ARCHITECTURE.md`.
- The demo that inspired this appears to have used a live mic with a limited set of words, not full speech-to-text. The bare-command rule comes from that.

## Status

- Working: the GSPro key commands (aim, club, map, view, close, continue, hold), club bag navigation, local players and bags synced with GSPro's locker, "start application" (launches GSPro and the Open Connect apps), and the GSPro menu sequences ("practice screen", "go to range", "end round").
- Working in the base: the actions and chains mechanism (`hfg/actions.py`), and the Game dropdown that picks the active plug-in.
- Plug-in split: the adapter contract exists (`hfg/adapter.py`), but nothing calls it yet. `app/listener.py` still dispatches phrases directly, and the GSPro code is still inside the base app. Next step: replace that dispatch with a loop over the plug-ins (see `docs/ARCHITECTURE.md`, Next steps).
- Priority now: screen identification and getting back home (see `HANDOFF.md`, "Planned: know the screen").
- Later: "play match" by clicking a fixed spot in GSPro's window. Plan is in `HANDOFF.md`.
- Not started: the Pure Play plug-in, and the layout tool.

## Open questions

- Does GSPro expose its play-match button to accessibility tools? That would make the click more reliable than fixed coordinates.
- Package name for the base: the code is in `app/`, and `hfg/` is a placeholder. Pick one before the GSPro code moves. Also: are plug-ins separate Python packages in this repo, or their own repos?

## Log

- Display: switched monitor 2 from duplicate to extend, which fixed the second monitor showing as a tiny box.
- Page rule: voice commands run only while the Voice page is open. Words are captured only while the Mic setup page is open. Other pages do neither. The mic itself stays open while the app runs, and the level bar lives on Mic setup.
- Added a "Preferences" page. It saves the baseline room noise (default 30 dB) and has a Calibrate button. Calibrate measures the room for 3 seconds and sets an offset so the room reads the baseline. The offset is saved, and the mic page and transcript then show real-scale dB. Sound-meter reference: quiet room about 30 dB, normal conversation about 55–65 dB, shouting about 80–90 dB, measured at about a meter.
- Preferences is now the MCT Constants table, ported in. Rows: baseline room noise, noise gate, level full scale, calibrate seconds, command window, and send keys at start. Most apply after a restart. Plan: purge unused rows later.
- Added a "Mic setup" page. It holds the mic chooser and a test that shows what's heard in a rolling text box. Test mode ignores commands, so it never sends keys to GSPro. (It first had a Vosk / Windows speech radio. Vosk was removed on 2026-11-15, and the radio went with it.)
- Dropdown shows one GSPro display entry because both monitors are the same model. GSPro launches on monitor 1 by selecting it.
- 2026-11-15: Plug-in split started. Architecture written in `docs/ARCHITECTURE.md`. Game dropdown and actions/chains added. Vosk dropped.
- 2026-11-16: Refreshed this doc: start phrase is now an option, Status updated, plug-in pointer added. Next code step is the listener loop over plug-ins.
