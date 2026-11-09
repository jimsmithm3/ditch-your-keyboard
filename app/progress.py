"""What a GSPro step is doing right now, for the Overview page and the status bar.

Background threads call set_working() and clear(). The GUI reads current() on a timer, so
no widget is touched from another thread.
"""

import threading

_lock = threading.Lock()
_text = ""


def set_working(text: str) -> None:
    global _text
    with _lock:
        _text = text


def clear() -> None:
    set_working("")


def current() -> str:
    with _lock:
        return _text
