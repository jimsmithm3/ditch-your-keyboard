"""The help boxes: "toggle overlay" draws a red box over each button on the GSPro screen the app thinks it is on,
labelled with what to say to press it. Only single clicks get a box. A chain ("click gspro practice range now") has no box,
since it presses several buttons. When one widget has more than one command, its box is labelled with them all,
separated by " | " (the search box holds "use filter" and "clear filter"; a course row holds "play row" and
"download row"). The boxes are click-through and take no focus, like the course legend (gspro_legend.py), and sit
above GSPro but under our app's windows.

The screen is the one the app remembers (gspro_sequences.current_screen). If it is not known, no boxes are drawn.
"""

import ctypes
import logging
import re

from PySide6.QtCore import QRect, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

from app import text_entry
from app.connector_ui import client_rect, find_window
from app.course_chooser import (
    said_course,
    DESCRIPTION_CLOSE,
    COURSE_LIST,
    HISTORY_CLOSE,
    PANEL_CLOSE,
    PANEL_PLAY,
    read_more_present,
    row_state,
    READ_MORE,
    ROUND_HISTORY,
    dialog_state,
    list_mode,
    notes_view_has_cancel,
)
from app.gspro_screens import RECORDS_BY_KEY, group_phrases
from app.gspro_sequences import COURSE_LIST_SCREENS, FILTER_VIEW, GAME_MENU_PANEL, NOTES_VIEW, SEQUENCES, current_panel, current_screen, current_view, randomizer_on, refresh_random
from app.gspro_ui import (
    CANCEL_BUTTON,
    CONFIRM_BUTTON,
    END_ROUND_BUTTON,
    MENU_BUTTON,
    MENU_CLOSE,
    SHOTS_1,
    SHOTS_15,
    WIND_DIRECTION_LEFT,
    WIND_MPH,
    WIND_RIGHT_X,
    WIND_STRENGTH_LEFT,
)
from app.gspro_ui import (
    ADDITIONAL_CARD,
    CHALLENGES_CARD,
    CLEAR_SEARCH_CLICK,
    FILTER_FAVORITES,
    FILTER_ALL,
    FILTER_INSTALLED,
    FILTER_TRENDING,
    GSPRO_TITLE,
    LOCAL_CARD,
    ON_COURSE_CARD,
    ONLINE_CARD,
    PRACTICE_CARD,
    RANGE_CARD,
    PREFERENCES_CHEVRON,
    ROUND_PLAY,
    SEARCH_BOX,
    TOURNAMENTS_CARD,
)

log = logging.getLogger(__name__)

REFRESH_MS = 500  # follows the screen and the GSPro window while the boxes are up
GW_HWNDPREV = 3  # the window just above another in the stack
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
CARD_SIZE = (0.16, 0.33)  # a button tile on the home or practice screen, as a fraction of the window
BUTTON_SIZE = (0.12, 0.06)  # any other button (BACK, EXIT)
CARDS = {LOCAL_CARD, PRACTICE_CARD, CHALLENGES_CARD, TOURNAMENTS_CARD, ONLINE_CARD, ON_COURSE_CARD, ADDITIONAL_CARD, RANGE_CARD}
# Two looks for the overlay. The red one is the default; overlay look swaps to the gentle blue one.
RED_LOOK = {
    "box": QColor(230, 30, 30), "width": 3, "label": QColor(160, 20, 20, 147),
    "text": QColor(255, 255, 255), "header": QColor(110, 110, 110),
}
GENTLE_LOOK = {
    "box": QColor(8, 40, 110), "width": 3, "label": QColor(190, 225, 250, 220),  # dark navy, so the box shows against the light label
    "text": QColor(15, 35, 60), "header": QColor(200, 205, 212),
}
_gentle = True  # the blue look is the default; "overlay red" switches to the red one
BOX_COLOUR = QColor(230, 30, 30)
BOX_WIDTH = 4
LABEL_COLOUR = QColor(255, 255, 255)
LABEL_BACKGROUND = QColor(160, 20, 20, 147)  # a third more transparent than 220


FONT_POINTS = 14  # the overlay label size; "overlay larger" and "overlay smaller" change it by one
FONT_MIN, FONT_MAX = 8, 28


def change_font(step: int) -> str:
    """Make the overlay labels bigger (step 1) or smaller (step -1). The window repaints on its next tick."""
    global FONT_POINTS
    FONT_POINTS = max(FONT_MIN, min(FONT_MAX, FONT_POINTS + step))
    log.info("overlay font: %d pt", FONT_POINTS)
    return f"Overlay font: {FONT_POINTS} pt"


def set_look(gentle: bool) -> str:
    """Set the help look: the red boxes, or the gentle blue ones. The window repaints on its next tick."""
    global _gentle, BOX_COLOUR, BOX_WIDTH, LABEL_BACKGROUND, LABEL_COLOUR, SCREEN_CMDS_HEADER_BG
    _gentle = gentle
    look = GENTLE_LOOK if _gentle else RED_LOOK
    BOX_COLOUR, BOX_WIDTH = look["box"], look["width"]
    LABEL_BACKGROUND, LABEL_COLOUR = look["label"], look["text"]
    SCREEN_CMDS_HEADER_BG = look["header"]
    log.info("help look set: %s", "blue" if _gentle else "red")
    return "Overlay: blue" if _gentle else "Overlay: red"



LABEL_MIN_WRAP_SHARE = 0.03  # a line wraps once it is wider than the box it labels, but never narrower than this (small icon boxes split into words)
LABEL_MAX_SHARE = 0.3  # a label is as wide as its text, up to this share of the window; past that it wraps onto more lines (help mode may cover the screen)
# Boxes that fit a control, not a tile: (left, top, width, height) as fractions of the window. Keyed by the widget.
# The notes view's own boxes that are not on the same spot as their click: the FILTERS button (upper right, shows once a row is clicked).
SHOW_FILTERS_BOX = (0.9131, 0.1041, 0.0748, 0.0445)
FIT_BOXES: dict[tuple[float, float], tuple[float, float, float, float]] = {
    FILTER_INSTALLED: (0.6988, 0.2473, 0.065, 0.039),  # the Installed pill
    # The notes view's details: the X, the Read More button, the scores icon and the big Play button.
    PANEL_CLOSE: (0.945, 0.165, 0.032, 0.07),
    READ_MORE: (0.9034, 0.612, 0.0655, 0.044),
    ROUND_HISTORY: (0.960, 0.748, 0.016, 0.025),  # the clipboard icon only (was 0.03 x 0.04, too big on the right and bottom)
    PANEL_PLAY: (0.6927, 0.8455, 0.2817, 0.044),  # the Play button: the top is right now; the bottom needs to go lower
    HISTORY_CLOSE: (0.648, 0.235, 0.026, 0.045),  # the X on the round history dialog
    ROUND_PLAY: (0.7955, 0.927, 0.176, 0.055),  # the big PLAY on round settings, bottom right
    PREFERENCES_CHEVRON: (0.3045, 0.0375, 0.0195, 0.036),  # just the chevron of the driving range panel
    MENU_BUTTON: (0.9605, 0.018, 0.03, 0.042),  # the hamburger, upper right: the show menu box sits on it
    MENU_CLOSE: (0.955, 0.0175, 0.03, 0.045),  # the X on the game menu
    CONFIRM_BUTTON: (0.398, 0.557, 0.0905, 0.0457),  # the CONFIRM button on the end round dialog
    CANCEL_BUTTON: (0.511, 0.557, 0.091, 0.0457),  # the Cancel button beside it
    DESCRIPTION_CLOSE: (0.6888, 0.644, 0.104, 0.046),  # the Close button on the read more dialog
    FILTER_ALL: (0.7705, 0.2473, 0.0475, 0.039),  # the All pill
    FILTER_TRENDING: (0.8244, 0.2473, 0.069, 0.039),  # the Trending pill
    FILTER_FAVORITES: (0.901, 0.2473, 0.0675, 0.039),  # the Favorites pill
    SEARCH_BOX: (0.0125, 0.100, 0.6405, 0.051),  # the whole search box: "use filter" and "clear filter" are both in it
}
# Phrases with no single click of their own, boxed where they act: (left, top, width, height) as fractions.
BOX_ONLY: dict[str, tuple[float, float, float, float]] = {
    "change driving range distance": (0.168, 0.03, 0.129, 0.06),  # the Driving Range Distance box, ending just past the slider
    "change wind": (0.49, 0.0, 0.075, 0.045),  # the wind arrow and speed at the top, as wide as that widget
    f"toggle hand": (0.013, 0.915, 0.066, 0.075),  # the RIGHT HAND button, lower left
}
# The chevron that closes the open driving range panel (top right of the panel).
CLOSE_PREFERENCES_BOX = (0.2883, 0.104, 0.0195, 0.036)
# The open driving range panel. Its boxes depend on the randomizer: on, the min and max sliders replace the
# distance box. The shot counts in the panel are not boxed yet: their positions are not measured.
PREFS_DISTANCE_BOX = (0.214, 0.275, 0.064, 0.042)  # the distance value box, with its pencil at the right
PREFS_MAX_BOX = (0.018, 0.378, 0.195, 0.034)  # the Max Distance track (randomizer on)
PREFS_MIN_BOX = (0.018, 0.430, 0.195, 0.034)  # the Min Distance track (randomizer on)
set_look(_gentle)  # the globals the painting reads must match the default look


def _prefs_panel_targets() -> list[tuple[str, tuple[float, float, float, float]]]:
    boxes: list[tuple[str, tuple[float, float, float, float]]] = [("close prefs", CLOSE_PREFERENCES_BOX)]
    if randomizer_on():
        boxes += [("change max distance", PREFS_MAX_BOX), ("change min distance", PREFS_MIN_BOX)]
    else:
        boxes.append(("type driving range distance | [0-9] | done", PREFS_DISTANCE_BOX))  # "done" completes the typed change
    boxes += [
        ("apply", (0.240, 0.478, 0.072, 0.040)),  # APPLY at the bottom of the panel
        ("random [on|off]", (0.105, 0.325, 0.02, 0.04)),  # the two arrows beside Randomizer On/Off
    ]
    if randomizer_on():
        # shown with the max and min distance, as they are: one box over the shot counts, right of the randomizer
        # (SHOTS_1 to SHOTS_15 on the same row), starting 20 px right of the old start
        boxes.append(("shots per [1|3|5|10|15]", (0.138, SHOTS_1[1] - 0.02, SHOTS_15[0] + 0.008 - 0.138, 0.04)))
    return boxes
# The open wind panel: each slider's track (press its left end, drag right) and the wind speed that closes it.
WIND_PANEL_BOXES: dict[str, tuple[float, float, float, float]] = {
    "change direction": (WIND_DIRECTION_LEFT[0] - 0.006, WIND_DIRECTION_LEFT[1] - 0.012, WIND_RIGHT_X - WIND_DIRECTION_LEFT[0] + 0.012, 0.03),
    "change strength": (WIND_STRENGTH_LEFT[0] - 0.006, WIND_STRENGTH_LEFT[1] - 0.012, WIND_RIGHT_X - WIND_STRENGTH_LEFT[0] + 0.012, 0.03),
    "close": (0.49, 0.0, 0.075, 0.045),  # the wind speed: a click on it closes the panel
}

# A phrase that presses the same button as another sequence: "play course" on round settings is PLAY, as "now" is.
BOX_CLICKS: dict[str, str] = {"play course": "now"}

# Clicks that are on the same widget as another command: the box is shared, labelled with both.
WIDGET_OF: dict[tuple[float, float], tuple[float, float]] = {CLEAR_SEARCH_CLICK: SEARCH_BOX}

_ROW_PHRASE = re.compile(r"^(play|download) row (\w+)$")  # "now" variants are chains, so they get no label of their own
_FAVORITE_PHRASE = re.compile(rf"^toggle favorite row (\w+)$")
_NOTES_PHRASE = re.compile(r"^show notes (\w+)$")


def _box(widget: tuple[float, float]) -> tuple[float, float, float, float]:
    """(left, top, width, height) as fractions of the window: a fitted box if there is one, else centred on the widget."""
    if widget in FIT_BOXES:
        return FIT_BOXES[widget]
    width, height = CARD_SIZE if widget in CARDS else BUTTON_SIZE  # every tile box is the same size
    return widget[0] - width / 2, widget[1] - height / 2, width, height


def _course_label(phrase: str) -> str:
    """"play <course>" on round settings: the name as the user said it, or a generic name if it was not said here."""
    said = said_course()
    return f"play {said}" if said else phrase.replace("<course>", "<course name>")


def _chooser_widget(phrase: str) -> tuple[tuple, tuple[float, float, float, float]] | None:
    """(widget key, box) for a course list command that is not a single sequence, or None."""
    if phrase == f"use filter":
        return SEARCH_BOX, FIT_BOXES[SEARCH_BOX]
    match = _ROW_PHRASE.match(phrase)
    if match and match.group(2) in COURSE_LIST.rows:
        kind, word = match.group(1), match.group(2)
        # Only the button the row shows is offered: Play on an installed course, Download on one not yet installed.
        if row_state(COURSE_LIST.number(word)) != ("play" if kind == "play" else "download"):
            return None
        return COURSE_LIST.box("button", word)
    match = _FAVORITE_PHRASE.match(phrase)
    if match and match.group(1) in COURSE_LIST.rows:
        # The favourite heart is only offered on an installed course's row.
        if row_state(COURSE_LIST.number(match.group(1))) != "play":
            return None
        return COURSE_LIST.box("favorite", match.group(1))
    match = _NOTES_PHRASE.match(phrase)
    if match and match.group(1) in COURSE_LIST.rows:
        if row_state(COURSE_LIST.number(match.group(1))) is None:
            return None  # an empty row has no notes
        return COURSE_LIST.box("notes", match.group(1))
    return None


def _notes_view_targets() -> list[tuple[str, tuple[float, float, float, float]]]:
    """The notes view's details: its own boxes. A dialog on top (read more, latest scores) is the only thing boxed while it is up."""
    dialog = dialog_state()
    if dialog == "read_more":
        return [("close", _box(DESCRIPTION_CLOSE))]
    if dialog == "latest_scores":
        return [("cancel", _box(HISTORY_CLOSE))]
    return [
        *([("cancel", _box(PANEL_CLOSE))] if notes_view_has_cancel() else []),  # additional driving ranges has no X
        *([("read more", _box(READ_MORE))] if read_more_present() else []),  # a course with no Read More has no button
        ("latest scores", _box(ROUND_HISTORY)),
        ("play course (now)", _box(PANEL_PLAY)),
        ("show filters", SHOW_FILTERS_BOX),  # the FILTERS button is there with the details open too
    ]


def _notes_preview_targets() -> list[tuple[str, tuple[float, float, float, float]]]:
    """The notes view on the right with no details open: its own Play and clipboard, and the FILTERS button."""
    return [
        ("play course (now)", _box(PANEL_PLAY)),
        ("latest scores", _box(ROUND_HISTORY)),  # the clipboard icon: opens a dialog with only a cancel
        ("show filters", SHOW_FILTERS_BOX),
    ]


def _shown_now(phrase: str) -> bool:
    """Some commands are only offered while their panel or menu is up, so they are not boxed before then."""
    if phrase == "close prefs":
        return current_panel() == "driving_preferences_panel"
    if phrase == "open prefs":
        return current_panel() != "driving_preferences_panel"
    return True


def _filter_phrase(phrase: str) -> bool:
    return phrase.startswith("filter ") or phrase in ("use filter", "clear filter")


def _wrong_mode(phrase: str, key: str | None) -> bool:
    """On the course list, the view read at entry decides. The filter pills are only on the filter view, so they are
    only boxed in filter mode. Everything else (the rows, the notes icons) is boxed in both modes. The notes view
    takes the same space as the filter view, so while it is up the filter boxes are not shown."""
    if key not in COURSE_LIST_SCREENS:
        return False
    if current_view() == NOTES_VIEW:
        return _filter_phrase(phrase)
    if list_mode() != "notes":
        return False
    return _filter_phrase(phrase)


def _filter_view_targets() -> list[tuple[str, tuple[float, float, float, float]]]:
    """The filter view's four pills. Its words add to the screen, like the notes view's."""
    return [
        ("filter installed", _box(FILTER_INSTALLED)),
        ("filter all", _box(FILTER_ALL)),
        ("filter trending", _box(FILTER_TRENDING)),
        ("filter favorites", _box(FILTER_FAVORITES)),
    ]


def targets(key: str | None) -> list[tuple[str, tuple[float, float, float, float]]]:
    """(label, box) for each widget the screen has a command for. The notes and filter views add their boxes to the
    screen's. A dialog on the notes view (read more, latest scores) is the only thing boxed while it is up."""
    if text_entry.active() and key in COURSE_LIST_SCREENS:
        return [("end filter", FIT_BOXES[SEARCH_BOX])]  # the filter is typing: it locks out the rest of the screen
    view = current_view()
    if view == NOTES_VIEW:
        if dialog_state():
            return _notes_view_targets()  # a dialog: only its own close is boxed
        return [*_notes_view_targets(), *_screen_targets(key)]
    if view == FILTER_VIEW:
        return [*_filter_view_targets(), *_screen_targets(key)]
    return _screen_targets(key)


def _screen_targets(key: str | None) -> list[tuple[str, tuple[float, float, float, float]]]:
    """The screen's own boxes. The label is the phrases for that widget, joined with " | "."""
    if current_panel() == "driving_preferences_panel":
        return _prefs_panel_targets()  # the open panel is its own screen: only its help
    if current_panel() == "end_round_confirm":
        return [("confirm", _box(CONFIRM_BUTTON)), ("cancel", _box(CANCEL_BUTTON))]  # the end round dialog
    if current_panel() == GAME_MENU_PANEL:
        return [("cancel", _box(MENU_CLOSE)), ("end round", _box(END_ROUND_BUTTON))]  # the game menu is its own screen: only its help
    if current_panel() == "wind_panel":
        return [(phrase, box) for phrase, box in WIND_PANEL_BOXES.items()]  # the wind panel's own commands only
    record = RECORDS_BY_KEY.get(key) if key else None
    if record is None:
        return []
    candidates: list[tuple[str, str]] = []
    for trans in record.trans:
        if not trans.sequence:
            continue
        if "<" in trans.phrase and not key.startswith("round_settings"):
            continue  # a course name is only typed on round settings; the list's own play is a chooser command
        candidates += [(alias, trans.sequence) for alias in trans.aliases]  # "play course": PLAY, said plainly
        candidates.append((_course_label(trans.phrase), trans.sequence))
    candidates += [(phrase, phrase) for phrase in record.phrases]
    for name in record.groups:
        candidates += [(phrase, phrase) for phrase in group_phrases(name)]
    boxes: dict[tuple, tuple[tuple[float, float, float, float], list[str]]] = {}
    gathered = _screen_cmds(key)  # these are in the screen cmds label, not boxed one by one
    for phrase, sequence in candidates:
        if phrase in gathered:
            continue
        if _wrong_mode(phrase, key):
            continue
        if phrase in BOX_ONLY:
            boxes.setdefault(("only", phrase), (BOX_ONLY[phrase], []))[1].append(phrase)
            continue
        if not _shown_now(phrase):
            continue  # close prefs only while the panel is open, cancel only while the menu is
        key_sequence = BOX_CLICKS.get(sequence, sequence)
        if key_sequence in SEQUENCES:
            steps = SEQUENCES[key_sequence]
            if len(steps) != 1 or not steps[0].click:
                continue
            widget = WIDGET_OF.get(steps[0].target, steps[0].target)
            found = (widget, _box(widget))
        else:
            found = _chooser_widget(phrase)
            if found is None:
                continue
        widget, box = found
        labels = boxes.setdefault(widget, (box, []))[1]
        if phrase not in labels:
            labels.append(phrase)
    # "use" and "play" come first: "use filter | clear filter", "play row one | download row one"
    # "play row N" is the shortcut-able one: "(now)" marks the word as optional, as on the round settings help
    labelled = [[f"{phrase} (now)" if phrase.startswith("play row ") else phrase for phrase in labels] for labels in (labels for _, labels in boxes.values())]
    result = [(" | ".join(sorted(words, key=lambda phrase: not phrase.startswith(("play", "use")))), box)
              for (box, _), words in zip(boxes.values(), labelled)]
    if key in COURSE_LIST_SCREENS and list_mode() == "notes" and current_view() != NOTES_VIEW:
        result.extend(_notes_preview_targets())  # the notes view on the right, with no details open
    return result


CONTINUATION = "  "  # two spaces at the start of a wrapped line, so it reads as part of the command above


def _wrap(metrics, command: str, max_w: int) -> list[str]:
    """The command split at word breaks so each line fits max_w. Lines after the first start with CONTINUATION.
    A single word wider than max_w is kept whole rather than cut."""
    lines: list[str] = []
    current = ""
    for word in command.split():
        if not current:
            current = word
        elif metrics.horizontalAdvance(f"{current} {word}") <= max_w:
            current = f"{current} {word}"
        else:
            lines.append(current)
            current = CONTINUATION + word
    if current:
        lines.append(current)
    return lines


CLUB_LIST_LEFT = 0.01  # the club list sits at bottom left, above the club tile
CLUB_LIST_TOP = 0.50
CLUB_LIST_BOTTOM = 0.92  # the list's red box runs down over the driver icon, the club tile at bottom left
# Commands gathered into one black label next to the game menu button, not boxed one by one on the screen.
SCREEN_CMDS = ("look left", "look right", f"toggle ui", f"toggle pin", "reset aim", f"toggle heat map", f"toggle green grid")  # end round is on the show game menu box
# How a command reads in the list where it differs: a look is ended by saying stop once it is where you want it.
SCREEN_CMDS_TEXT: dict[str, str] = {"look left": "look left → stop", "look right": "look right → stop"}
# How a command reads on its label where it differs from the phrase. "→ stop" says to say stop once a drag is where
# you want it; "<...>" marks a shortcut that goes through more than one screen or step.
LABEL_EXTRAS: dict[str, str] = {
    "change driving range distance": "change driving range distance → stop | slide left|right → stop",
    "change direction": "change direction → stop",
    "change strength": "change strength → stop",
    "change max distance": "change max distance → stop | slide left|right → stop",
    "change min distance": "change min distance → stop | slide left|right → stop",
    "end round": "<end round>",
    "skip to gspro practice range": "<skip to gspro practice range>",
    "skip to on course practice": "<skip to on course practice>",
    "skip to additional ranges": "<skip to additional ranges>",
}
SCREEN_CMDS_TOP = 0.009  # the top of the screen cmds, at the top right
SCREEN_CMDS_RIGHT = 0.83  # the right edge of the set: just left of the Practice Range header, with a buffer; longer lines grow to the left
SCREEN_CMDS_HEADER_BG = QColor(110, 110, 110)  # the grey heading; the commands below it are red like other help


def _club_lines() -> list[str]:
    from app.bag import CATALOG

    names = ["club up", "club down", "club putter"] + [club.phrases[0] for club in CATALOG]
    return list(dict.fromkeys(names))


def _has_club(key: str | None) -> bool:
    record = RECORDS_BY_KEY.get(key) if key else None
    return record is not None and "Club" in record.groups


def _screen_cmds(key: str | None) -> list[str]:
    """The SCREEN_CMDS this screen has, in their order. Only hitting screens have them."""
    record = RECORDS_BY_KEY.get(key) if key else None
    if record is None or "hitting_base" not in record.groups:
        return []
    have = set(record.phrases)
    for name in record.groups:
        have.update(group_phrases(name))
    return [phrase for phrase in SCREEN_CMDS if phrase in have]


def _draw_screen_cmds(painter, width: int, height: int, key: str | None) -> None:
    """A vertical list: a grey heading, then each command on a red line. Each line is only as wide as its text."""
    phrases = _screen_cmds(key)
    if not phrases:
        return
    metrics = painter.fontMetrics()
    line_h = metrics.height()
    right = int(SCREEN_CMDS_RIGHT * width)
    top = int(SCREEN_CMDS_TOP * height)
    lines = [("screen cmds", SCREEN_CMDS_HEADER_BG), *((SCREEN_CMDS_TEXT.get(phrase, phrase), LABEL_BACKGROUND) for phrase in phrases)]
    widest = max(metrics.horizontalAdvance(text) + 12 for text, _ in lines)
    left = right - widest  # the set grows to the left as its longest line grows
    # one red border round the whole set, padded; the blocks sit inside it, left-aligned
    pad = 4
    block_h = line_h + 6
    set_h = len(lines) * block_h + (len(lines) - 1) * 2
    painter.setPen(QPen(BOX_COLOUR, BOX_WIDTH))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRect(left - pad, top - pad, widest + 2 * pad, set_h + 2 * pad)
    y = top
    for text, background in lines:
        w = metrics.horizontalAdvance(text) + 12
        painter.fillRect(QRect(left, y, w, block_h), background)
        painter.setPen(LABEL_COLOUR)
        painter.drawText(left + 6, y + 3 + metrics.ascent(), text)
        y += block_h + 2


def _draw_club_list(painter, width: int, height: int) -> None:
    lines = _club_lines()
    per_column = (len(lines) + 1) // 2
    metrics = painter.fontMetrics()
    x0, y0 = int(CLUB_LIST_LEFT * width), int(CLUB_LIST_TOP * height)
    # rows are spread so the list reaches down over the club icon, and never shorter than the text
    row_h = max(metrics.height() + 4, int((CLUB_LIST_BOTTOM - CLUB_LIST_TOP) * height) // per_column)
    # each column is as wide as its longest name, so the second column starts after the first
    col_widths = [max(metrics.horizontalAdvance(line) + 12 for line in lines[c * per_column:(c + 1) * per_column]) for c in range(2)]
    col_x = [x0, x0 + col_widths[0] + 6]
    painter.setPen(QPen(BOX_COLOUR, BOX_WIDTH))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRect(x0, y0, col_x[1] + col_widths[1] - x0, row_h * per_column)
    for index, line in enumerate(lines):
        column, row = divmod(index, per_column)
        x, y = col_x[column], y0 + row * row_h
        painter.fillRect(QRect(x, y, metrics.horizontalAdvance(line) + 12, row_h - 2), LABEL_BACKGROUND)
        painter.setPen(LABEL_COLOUR)
        painter.drawText(x + 6, y + metrics.ascent() + 2, line)


class _Boxes(QWidget):
    def __init__(self) -> None:
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
            | Qt.WindowType.WindowTransparentForInput
        )
        super().__init__(None, flags)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt name)
        painter = QPainter(self)
        width, height = self.width(), self.height()
        font = QFont()
        font.setPointSize(FONT_POINTS)
        font.setBold(True)
        painter.setFont(font)
        for label, (left, top, box_w, box_h) in targets(current_screen()):
            if label == "show game menu":
                label = "show game menu | end round"  # end round is opened from the same button, so it reads with it
            if label == "begin practice":
                label += " | skip to gspro practice range | skip to on course practice | skip to additional ranges"
            label = " | ".join(LABEL_EXTRAS.get(part, part) for part in label.split(" | "))
            x0, y0 = int(left * width), int(top * height)
            x1, y1 = int((left + box_w) * width), int((top + box_h) * height)
            painter.setPen(QPen(BOX_COLOUR, BOX_WIDTH))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(x0, y0, x1 - x0, y1 - y0)
            metrics = painter.fontMetrics()
            # One line per command: a label joins a widget's commands with " | ". A command too wide for its box wraps
            # onto more lines at word breaks; those continuation lines start with two spaces, so they read as part of
            # the command above them. Wrapping is never narrower than LABEL_MIN_WRAP_SHARE and never wider than LABEL_MAX_SHARE.
            wrap_w = min(max(x1 - x0, int(LABEL_MIN_WRAP_SHARE * width)), int(LABEL_MAX_SHARE * width))
            lines: list[str] = []
            for command in label.split(" | "):
                lines += _wrap(metrics, command, wrap_w - 12)
            block_w = max(metrics.horizontalAdvance(line) for line in lines) + 12
            x0 = max(0, min(x0, width - block_w))  # a label at the right edge (show game menu) stays on the window
            line_h = metrics.height()
            painter.fillRect(QRect(x0, y0, block_w, line_h * len(lines) + 8), LABEL_BACKGROUND)
            painter.setPen(LABEL_COLOUR)
            for index, line in enumerate(lines):
                painter.drawText(x0 + 6, y0 + 4 + index * line_h + metrics.ascent(), line)
        if _has_club(current_screen()) and not current_panel():
            _draw_club_list(painter, width, height)
        if not current_panel():  # the screen cmds are live only with no panel up; a panel has its own help
            _draw_screen_cmds(painter, width, height, current_screen())
        painter.end()


_widget: _Boxes | None = None
_timer: QTimer | None = None


def _place() -> bool:
    """Cover the GSPro window and sit just above it in the stack. False if GSPro is not there."""
    hwnd = find_window(GSPRO_TITLE)
    if hwnd is None:
        return False
    left, top, right, bottom = client_rect(hwnd)
    above = ctypes.windll.user32.GetWindow(hwnd, GW_HWNDPREV)
    ctypes.windll.user32.SetWindowPos(
        int(_widget.winId()), above or 0, left, top, right - left, bottom - top, SWP_NOACTIVATE | SWP_SHOWWINDOW
    )
    return True


_shown = False  # the boxes are on the screen: what "toggle overlay" must go by, not the listener's own flag
_missed = 0  # refreshes in a row that did not find GSPro
MISSED_LIMIT = 3  # a brief miss (GSPro changing window) does not drop the help; this many in a row does


def is_showing() -> bool:
    return _shown


def _refresh() -> None:
    global _missed
    if _widget is None or not _widget.isVisible():
        return
    if _place():
        _missed = 0
        refresh_random()  # while the prefs panel is up, follow the switch as GSPro shows it
        _widget.update()
    else:
        _missed += 1
        if _missed >= MISSED_LIMIT:
            log.info("help boxes: GSPro not found for %d refreshes; hiding", _missed)
            hide()


def show() -> None:
    global _widget, _timer, _shown, _missed
    if _widget is None:
        _widget = _Boxes()
        _timer = QTimer(_widget)
        _timer.timeout.connect(_refresh)
    _widget.show()  # shown first so the window exists; _place then moves it over GSPro
    if _place():
        _missed = 0
        _shown = True
        _widget.update()
        _timer.start(REFRESH_MS)
        log.info("help boxes: shown")
    else:
        hide()
        log.info("help boxes: GSPro not found; not shown")


def hide() -> None:
    global _shown
    _shown = False
    if _timer is not None:
        _timer.stop()
    if _widget is not None:
        _widget.hide()
    log.info("help boxes: hidden")


def apply(shown: bool) -> None:
    """Called on the GUI thread, with what the listener sends."""
    if shown:
        show()
    else:
        hide()
