"""Entry point. Run from the project root: python main.py"""

import sys

from PySide6.QtWidgets import QApplication

from app.logging_setup import setup_logging
from app.main_window import MainWindow


def main() -> None:
    setup_logging()
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    raise SystemExit(app.exec())


if __name__ == "__main__":
    main()
