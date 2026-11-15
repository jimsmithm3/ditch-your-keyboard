# Splitting the base app from the game plug-ins

Working name for the base: "hands free gaming" (`hfg/`). The first plug-in is GSPro.

## What stays in the base
- Voice: `wsapi_recognizer.py`, `wsapi_grammar.py`, the listening on/off and wake words.
- Grammars: building them from groups, panels and screens (the mechanism, not the contents).
- Command model: `Command` rows, aliases, the commands page, the active-commands view.
- Panels and overlays: the mechanism that makes one grammar replace another while a panel is open.
- Text entry (`text_entry.py`), preferences, logging, window placement, startup, the shell.

## What moves behind an adapter (GSPro)
- Window find and focus (`focus.py`, `connector_ui.py`), and the connector setup.
- Clicks and keys (`clicks.py` calls stay, but the points and keys come from the adapter).
- Screen memory and the screen tree (`gspro_tree.py`, `gspro_screens.py`, `gspro_sequences.py`).
- Map geometry, the grid and the legend (`gspro_grid.py`, `gspro_legend.py`, `gspro_overlay.py`, `gspro_ui.py`).
- Course list and GSPro's database (`gspro_courses.py`), launch (`launch.py`).
- Chooser and wind/marker/hole panels (`course_chooser.py`, `bag.py`, `shadows.py`).

## Order of work
1. Done on this branch: `hfg/adapter.py` defines the boundary. Nothing uses it yet.
2. Replace the if-chain in `listener.py` with a loop over the registered adapters. The base handles its own phrases
   (listening on/off, commands dialog) first, then asks each adapter. This is the step that proves the split.
3. Make `gspro` an adapter: `gspro/adapter.py` implements `GameAdapter` by calling the existing modules unchanged.
4. Move the GSPro modules into `gspro/` once the adapter works, so the boundary is also a folder boundary.
5. Layout tool: store boxes and command placement as data per game (`layout()`), so Pure Play brings its own file.

## Risks
- `commands.py` and `gspro_sequences.py` are large and carry GSPro keys in the command rows. Moving them is the bulk of step 3.
- Screen memory and the panel rules are tangled with the clicks. Keep behaviour identical in each step and test in GSPro after each one.
- The GSPro window fractions in `gspro_ui.py` were measured by hand, so they must travel with the GSPro adapter.
