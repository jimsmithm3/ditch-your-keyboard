"""Entry point. Run from the project root: python main.py"""

import sys

from PySide6.QtCore import QEvent, QObject
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


def main() -> None:
    setup_logging()
    app = QApplication(sys.argv)
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
