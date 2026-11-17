"""Reading colours off the GSPro window, from the screen itself (Windows GetPixel). No Qt here.

A button's colour says what it is: blue is Play (the course is installed), grey is Download, anything else is no button.
"""

import ctypes


def pixel_colour(x: int, y: int) -> tuple[int, int, int]:
    """The (red, green, blue) of the screen at x, y."""
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    dc = user32.GetDC(0)
    try:
        color = gdi32.GetPixel(dc, x, y)
    finally:
        user32.ReleaseDC(0, dc)
    return color & 0xFF, (color >> 8) & 0xFF, (color >> 16) & 0xFF


def classify_button(red: int, green: int, blue: int) -> str | None:
    """"play" for the blue Play button, "download" for the grey Download button, None for anything else."""
    if blue > 150 and blue - red > 60:
        return "play"  # the blue Play button
    if max(red, green, blue) - min(red, green, blue) <= 14 and 60 <= red <= 170:
        return "download"  # the grey Download button; the dark background is none of these
    return None


def is_play_button(x: int, y: int) -> bool:
    """A Play button is blue. A Download button is grey, so a blue pixel means the course is installed."""
    return classify_button(*pixel_colour(x, y)) == "play"
