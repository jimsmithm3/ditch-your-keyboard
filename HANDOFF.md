# gspraudio handoff

Hands-free voice caddie for GSPro. PySide6 window, Vosk speech, keystrokes into the GSPro window. Python 3.14. Project root `C:\dev\gspraudio`. Run `main.py` from that root in PyCharm (SDK "Python 3.14 (gspraudio)"). Do not rebuild `dist\gspraudio.exe` unless asked. Do not commit unless asked.

Copy the whole project folder to the other computer. A git clone is not enough: `models/`, `gspraudio.db`, and `current_bag.txt` are gitignored, and this work may be uncommitted. Recreate `.venv` on the other machine rather than copying it. Use `PySide6_Essentials` and `shiboken6` only. Do not install the `PySide6` metapackage; it pulls WebEngine and has deleted `PySide6/__init__.py` before.

## Run

- Venv: `C:\dev\gspraudio\.venv`
- Wake words: "hey caddie" or "hey caddy". "gspraudio" is not in the small Vosk lexicon.
- Model: `models/vosk-model-small-en-us-0.15`
- Send keys defaults on.
- One mic thread. Prefer DirectSound. Open 16000 Hz or resample. Do not call sounddevice from the GUI thread.
- Focus GSPro once per command (`app/focus.py`: title contains "gspro", AttachThreadInput). On failure, do not send keys; the status bar says why. Do not re-focus between keys.
- Main window UI is `ui/main_window.ui` loaded with QUiLoader. Dialogs are built in code.
- Log: `logs/gspraudio.log`

## Voice

Grammar is wake phrases plus commands plus the active player's club phrases and nicknames. No `[unk]` in the grammar. Longest contained phrase wins. After a bare wake, the window turns light green for 5 seconds. A wake plus a command in the same phrase does not flash green. Recognizer is rebuilt when the player changes. Nicknames only work if every word is in the Vosk model.

"Continue" on aim left/right, zoom in/out, and tee left/right holds that key down until "hey caddy stop" or "hey caddie stop". It is one `keyDown`, not repeated taps. The key is released on stop, on another command, on player or mic change, if send-keys is turned off, and when the app closes. A counted phrase ("aim left five") is still separate presses, one through ten. Bare phrase is one press.

"Close" presses the last closable command again. Closable: expand map (S), flyover (O), scorecard (T), range finder (R). Close is not stored as the last command, so a second close toggles again. Nothing closable yet: status "Nothing to close".

## Clubs

Bag order, driver toward putter: Driver, 3 wood, 5 wood, 3–9 iron, Utility iron last among irons, Pitching, Gap, Sand, 56, Lob, Putter. I steps toward the putter. K steps toward the driver. Saying "putter" sends U once and remembers that index. Saying putter again does not send U. A repeated non-putter club, when the putter is in the bag, sends U then K back to that club. With no putter, it walks K to the driver and I back up. Reset club is still K back to the driver.

Edit bag is four columns (Woods, Irons, Wedges, Other), no scroll. Count label turns red over 14 clubs but save is still allowed. Empty selection is blocked. Utility iron and 56 wedge are gspraudio-only. They are not in GSPro's 27-club enum and do not persist in the player database.

## Players and bags

Local database: `gspraudio.db` next to the project (stdlib sqlite3).

- `player`: id, name, `bag_id` (GSPro locker bag id, nullable)
- `player_club`: player_id, club_index, active, nickname
- `app_state` key `player`: last player used

Startup uses that last player and loads their clubs and nicknames. Change user always opens the dialog. The dialog has Who is playing, a Bag dropdown filled from that player's saved GSPro bag (or the locker bag whose clubs still match), Use player, a horizontal line, then New player (name plus GSPro bag). Create copies that locker bag's clubs and nicknames into `player_club` and stores `bag_id`. Changing the bag dropdown and clicking Use player only updates `bag_id`. It does not replace the saved clubs.

GSPro locker database, read for the bag lists and written only by the GSPro bag shortcut dialog: `C:\Users\jim\AppData\LocalLow\GSPro\GSPro\GSPro.db`, table `LockerBag`. Club JSON is compact. Nickname saves must keep `separators=(",", ":")` so distances are not rewritten. `ClubNickName` is not set by the Open Connect API. Spoken nicknames live in our database. `resources/gspro_clubs.json` is the 27-club enum. 3 iron is index 15 and is not in Jim's locker bag.

Known local players from this machine: jim and bob. Jim has nicknames on 3 Hybrid ("nibblet") and 5 iron ("fiver").

`current_bag.txt` is only the fallback when no player exists.

## GSPro keys that matter

Esc is Show UI, and only when a course or practice HUD was hidden in settings. It is not the menu. The menu is the four-dot button. H hides the UI. Practice-only, and wired: 8 go to ball, 9 previous hole, 0 next hole. Camera go-to-ball is 5 and is still unwired.

Unwired rows stay in the commands table with a light red background and are not in the grammar. Areas, in open order: Aim, Club, Map, View, Mulligan, Camera, Practice, Visual / System. Columns: Area, Keystroke, Voice command, Description, Close, Continue. Click a header to sort.

## Open Connect

`GSPconnect.exe` listens on `127.0.0.1:921`. One heartbeat was accepted and logged, and nothing was sent back. Do not send a shot into a live round. The socket is shot data in, and replies 200 (shot received) and 201 (hand, club, sometimes distance to pin). The connector also has codes 202 and 203, which are not in the public docs. There is no bag or nickname API on that socket. Docs: https://gsprogolf.com/GSProConnectV1.html

## Files

- `app/commands.py` — phrase, key, area, wired, repeat, closes
- `app/listener.py` — mic, grammar, hold, close, player switch
- `app/bag.py` — catalog order and club steps
- `app/bag_dialog.py` — edit active clubs
- `app/commands_dialog.py` — command table
- `app/players.py` / `app/player_dialog.py` — local players and bags
- `app/gspro_bag.py` / `app/gspro_bag_dialog.py` — locker bags and shortcut edit
- `app/focus.py` — one focus before keys
- `app/main_window.py` — player, bag summary, status bar, buttons
- `resources/gspro_clubs.json` — GSPro club enum
- `gspraudio.spec` — PyInstaller datas: `ui/`, `models/`, `resources/`

## Left alone on purpose

Do not wire the red command rows unless asked. The GSPro bag dialog writes locker nicknames only. It does not update `gspraudio.db` or rebuild the recognizer. Player nicknames are the ones copied at create time, then heard after a restart or a player switch. README is stale. Esc doing nothing in GSPro was not a gspraudio bug.

## Open work: "play match" (planned, not built)

Goal: a voice command "play match" clicks GSPro's play-match button at a predefined spot, since GSPro has no API for it. Not started in code yet.

Setup and constraints:

- Dev machine has two monitors. Monitor 1 (LG HDR 4K, 3840x2160, 150% scaling) runs GSPro. Monitor 2 is the dev screen. Taskbar is on both. Monitor 2 was fixed by switching Multiple displays to Extend; it had been in duplicate mode.
- GSPro's display dropdown lists only one entry, because both monitors are the same model. Launch GSPro on monitor 1 by selecting that entry, or make monitor 1 the main display if it lands on the wrong screen.
- Keystrokes go to the focused window, not to a monitor. Mouse clicks depend on screen position.

Plan:

- Click relative to GSPro's window (find handle, read its rect, click at a fixed offset), not at fixed screen coordinates.
- Keep GSPro windowed or borderless, not exclusive fullscreen, with a fixed size and position.
- Make gspraudio DPI-aware so coordinates match the 150% scaling.
- Before clicking, confirm GSPro is foreground and in the expected spot. If not, skip the click and report it in the status bar.
- Check the click spot once with a screenshot before relying on it.
- Open question: does GSPro expose the button to accessibility tools (UI Automation, by name)? If so, prefer that over coordinates.
