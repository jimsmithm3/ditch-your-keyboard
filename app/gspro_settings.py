"""Which side GSPro's mini map is on, read from GSPro's own settings file at startup.

GSPro keeps its settings in Settings.vgs, a binary .NET file. The side is one 4-byte number just after the
course path text "GSProV1\\Core\\GSP\\Courses": 1 is the left side, 2 the right. The file is only read, never
written. If the file or the number is not what we expect, the right side is assumed and a warning is logged.
"""

import logging
from pathlib import Path

log = logging.getLogger(__name__)

SETTINGS_FILE = Path.home() / "AppData" / "LocalLow" / "GSPro" / "GSPro" / "Settings.vgs"
ANCHOR = rb"GSProV1\Core\GSP\Courses"  # the text the side number follows
LEFT_VALUE, RIGHT_VALUE = 1, 2

_side: str | None = None


def read_map_side() -> str:
    """Read the side from GSPro's settings file, remember it, and return "left" or "right"."""
    global _side
    try:
        data = SETTINGS_FILE.read_bytes()
    except OSError:
        log.warning("could not read GSPro's settings file; assuming the mini map is on the right")
        _side = "right"
        return _side
    at = data.find(ANCHOR)
    if at < 0 or data.find(ANCHOR, at + 1) >= 0:
        log.warning("GSPro's settings layout is not what the app expects; assuming the mini map is on the right")
        _side = "right"
        return _side
    value = int.from_bytes(data[at + len(ANCHOR): at + len(ANCHOR) + 4], "little")
    if value == LEFT_VALUE:
        _side = "left"
    elif value == RIGHT_VALUE:
        _side = "right"
    else:
        log.warning("GSPro's mini map side value is %d, not known; assuming the right side", value)
        _side = "right"
    log.info("GSPro's mini map is on the %s side", _side)
    return _side


def map_side() -> str:
    """"left" or "right". Read from the settings file the first time it is asked for, if not read already."""
    return _side if _side is not None else read_map_side()
