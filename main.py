"""Entry point. Run from the project root: python main.py"""

import faulthandler
import sys
import threading
import time
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, QTimer
from PySide6.QtWidgets import QApplication

from app.logging_setup import setup_logging
from app.main_window import MainWindow
from app.screen_table_dialog import show_screen_table
from app.window_places import MAIN_KEY, remember, restore


class _QuitWithMain(QObject):
    """The Commands window is a separate window, and Qt keeps running while any window is open. Closing the
    main window ends the whole app, so the console does not stay behind."""

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.Close:
            QApplication.quit()
        return False


HANG_SECONDS = 10  # the window has not answered for this long: write every thread's stack
STACK_FILE = Path(__file__).resolve().parent / "logs" / "hang_stacks.log"


def _watch_for_hang(beat: list[float], stacks) -> None:
    """Runs on its own thread. The window's timer keeps beat[0] fresh; if it goes stale, the GUI thread is stuck,
    so the stacks of all threads are written to the file (once per hang)."""
    written = False
    while True:
        time.sleep(1)
        stale = time.monotonic() - beat[0]
        if stale > HANG_SECONDS and not written:
            stacks.write(f"\n{time.ctime()}: window silent for {stale:.0f} s; stacks of all threads follow\n")
            faulthandler.dump_traceback(file=stacks, all_threads=True)
            stacks.flush()
            written = True
        elif stale <= HANG_SECONDS:
            written = False


def main() -> None:
    setup_logging()
    STACK_FILE.parent.mkdir(exist_ok=True)
    stacks = open(STACK_FILE, "a", encoding="utf-8")
    faulthandler.enable(file=stacks, all_threads=True)  # a hard crash writes its stacks here too
    app = QApplication(sys.argv)
    beat = [time.monotonic()]
    heartbeat = QTimer(app)
    heartbeat.timeout.connect(lambda: beat.__setitem__(0, time.monotonic()))  # only runs while the window is answering
    heartbeat.start(1000)
    threading.Thread(target=_watch_for_hang, args=(beat, stacks), daemon=True, name="ditch-your-keyboard-hang-watch").start()
    window = MainWindow()
    restore(window.window, MAIN_KEY)  # before show, so the window opens where it was
    remember(window.window, MAIN_KEY)
    quit_with_main = _QuitWithMain(window.window)
    window.window.installEventFilter(quit_with_main)
    window.show()
    if window.listener is not None:
        show_screen_table(None)  # the Commands window opens at startup, where it was
    raise SystemExit(app.exec())


if __name__ == "__main__":
    main()
