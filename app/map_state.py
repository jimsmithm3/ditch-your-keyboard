"""Read the mini map's size from the screen: large, small, or unknown.

The map header is a dark bar. Its title sits in a fixed place: near the top when the map is large, halfway down when
it is small. White title text at the expected place, and no white text at the other, confirms which one it is. On
the left side of the screen everything is mirrored (x becomes 1 - x). Anything else is unknown: the collapsed map,
a different layout, or a screen not in view. Positions are fractions of the GSPro window.
"""

from collections.abc import Callable

Pixel = tuple[int, int, int]
Probe = Callable[[float, float], Pixel]  # colour at a window fraction

SMALL_TITLE = (0.921, 0.546)  # the "Tee" title when the map is small, right side
LARGE_TITLE = (0.855, 0.117)  # the same title when the map is large, right side
SMALL_BAR = (0.90, 0.546)  # dark header bar beside the small title
LARGE_BAR = (0.74, 0.117)  # dark header bar beside the large title
TITLE_HALF = 0.012  # the box searched for white title text, half its width and height
WHITE_SHARE = 0.10  # at least this share of the box must be white for title text to be there
GRID = 12  # samples per side inside the box

LARGE, SMALL, UNKNOWN = "large", "small", "unknown"


def _is_white(pixel: Pixel) -> bool:
    return all(channel > 200 for channel in pixel)


def _is_dark_bar(pixel: Pixel) -> bool:
    red, green, blue = pixel
    return red < 60 and green < 70 and blue < 90 and blue >= red


def _title_white(probe: Probe, cx: float, cy: float) -> bool:
    white = 0
    for row in range(GRID):
        for col in range(GRID):
            fx = cx - TITLE_HALF + 2 * TITLE_HALF * col / (GRID - 1)
            fy = cy - TITLE_HALF + 2 * TITLE_HALF * row / (GRID - 1)
            if _is_white(probe(fx, fy)):
                white += 1
    return white / (GRID * GRID) >= WHITE_SHARE


def read_map_state(probe: Probe) -> str:
    """LARGE or SMALL when the screen shows exactly one of them on either side, otherwise UNKNOWN."""
    found = set()
    for mirror in (False, True):
        def at(fx: float, fy: float, _m=mirror) -> Pixel:
            return probe(1 - fx if _m else fx, fy)

        small_title = _title_white(at, *SMALL_TITLE)
        large_title = _title_white(at, *LARGE_TITLE)
        if small_title and not large_title and _is_dark_bar(at(*SMALL_BAR)):
            found.add(SMALL)
        if large_title and not small_title and _is_dark_bar(at(*LARGE_BAR)):
            found.add(LARGE)
    return found.pop() if len(found) == 1 else UNKNOWN
