# Ditch Your Keyboard: architecture

Ditch Your Keyboard is a hands-free voice layer for PC games. The base app listens, understands phrases, shows what is
listening, and handles panels, overlays and saved settings. It knows nothing about a particular game. Each game is a
plug-in that tells the base app what its screens look like and how to act in the game.

The first plug-in is GSPro (a golf simulator). Pure Play, another golf simulator, is planned as a second plug-in.

## Layers

```
 +-----------------------------------------------------------+
 |  Base app (Ditch Your Keyboard)                            |
 |  voice: recogniser, grammar building, listening on/off     |
 |  commands: command table, aliases, commands page           |
 |  panels & overlays: one grammar replaces another while a   |
 |  panel is open; overlays drawn over the game window        |
 |  settings, logging, text entry, window placement, startup  |
 +-----------------------------+-----------------------------+
                               |  GameAdapter (hfg/adapter.py)
        +----------------------+----------------------+
        |                                             |
 +------+-----------+                        +--------+---------+
 | GSPro plug-in    |                        | Pure Play plug-in|
 | screens, clicks, |                        | (planned)        |
 | grid, courses,   |                        |                  |
 | launch, connector|                        |                  |
 +------------------+                        +------------------+
```

## The contract a plug-in provides

`hfg/adapter.py` defines it. A plug-in implements these, and the base app calls nothing else:

- `find_window()` and `focus(window)`: find the game and bring it to the front. Nothing is sent if focus fails.
- `click(window, point, label)` and `press(keys, label)`: act in the game. Points are fractions of the game window, so a
  layout works at any window size.
- `current_screen()`: the screen the game is on, as far as the plug-in knows (or `None`).
- `commands()`: every command, for the commands page.
- `grammars()`: which phrases listen on each screen or panel.
- `layout()`: boxes and where each command sits on each screen. This is the data a future layout tool draws and edits.
- `handle(phrase, on_done)`: run a phrase the plug-in owns. Return a note, or `None` so the next plug-in can try.

Registration is `register(adapter)`. The base app asks registered plug-ins in order; the first one that handles a
phrase wins.

## What belongs where

| Base app | Plug-in |
|---|---|
| recogniser, grammar building, listening on/off, wake words | the game's screens and what they listen for |
| command table mechanism, aliases, commands page | the commands themselves (their keys and clicks) |
| panel and overlay mechanism | the panels, their positions and their contents |
| settings, logging, text entry, window placement, startup | the game's window title, database, launch and connector |

## Plug-in layout (planned)

Each plug-in is its own project, so it can be developed and versioned separately. The base app loads the plug-ins
the user has enabled. A plug-in is a Python package with an `adapter.py` that exposes one `GameAdapter`, plus its
layout data. Plug-ins use only the base app's own packages and the standard library, so they never pin a conflicting
dependency.

## Data

- Settings and the base app's own tables live in one database, `ditch-your-keyboard.db` (renamed from
  `gspraudio.db`; the first run copies the old file).
- Each plug-in keeps its own keys in that database, prefixed with the plug-in name, so two plug-ins never collide.
- Reference screenshots stay out of the bundle. Only the layout data a plug-in needs at run time ships with it.

## Size and start-up

The bundled app is dominated by PySide6. Plug-in code is a few kilobytes each, so many plug-ins barely change the
download size. The things that do matter are start-up time (load only enabled plug-ins), dependency clashes (keep
plug-ins light), and asset weight (keep screenshots out of the bundle).

## Status

- Done: the project is renamed; the adapter boundary is defined in `hfg/adapter.py`; the split is planned in
  `docs/adapter-split.md`.
- Not yet: nothing calls the adapter. The base app still dispatches phrases through a long `if` chain in
  `app/listener.py`, and the GSPro code is still inside the base app.

## Next steps

1. Replace the `if` chain in `app/listener.py` with a loop over registered plug-ins. The base app handles its own
   phrases first (listening on/off, the commands dialog), then asks each plug-in.
2. Make GSPro a plug-in: `gspro/adapter.py` implements `GameAdapter` by calling the existing modules unchanged.
3. Move the GSPro modules into `gspro/` once the adapter works, so the boundary is also a folder boundary.
4. Layout tool: store boxes and command placement as data per game, so Pure Play brings its own file.

## Open decisions

- Package name. The base code is still in `app/`, and `hfg/` is a placeholder name for the boundary. Pick one name
  before step 3, so the folders do not have to move twice.
- Whether plug-ins are separate Python packages in the same repo or their own repos. Separate repos suit "each
  plug-in tracked in its own project"; the same repo is simpler while there is one plug-in.
