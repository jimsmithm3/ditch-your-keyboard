"""Entry point. Run from the project root: python main.py"""

import sys

from PySide6.QtWidgets import QApplication

from app.logging_setup import setup_logging
from app.main_window import MainWindow
from app.screen_table_dialog import show_screen_table
from app.window_places import MAIN_KEY, remember, restore


def main() -> None:
    setup_logging()
    app = QApplication(sys.argv)
    window = MainWindow()
    restore(window.window, MAIN_KEY)  # before show, so the window opens where it was
    remember(window.window, MAIN_KEY)
    window.show()
    if window.listener is not None:
        show_screen_table(None)  # the Commands window opens at startup, where it was
    raise SystemExit(app.exec())


if __name__ == "__main__":
    main()
