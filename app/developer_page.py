"""Developer page: switches for testing gspraudio without disturbing GSPro."""

from PySide6.QtWidgets import QCheckBox, QLabel, QVBoxLayout, QWidget

from app import focus
from app.prefs import get_bool, set_bool

TEST_MODE_KEY = "test_mode"


def build_developer_page() -> QWidget:
    page = QWidget()
    layout = QVBoxLayout(page)

    test_mode = QCheckBox("Test gspraudio: don't unminimize GSPro")
    # Restore the saved choice before connecting, so startup doesn't re-save it.
    test_mode.setChecked(get_bool(TEST_MODE_KEY, False))
    focus.set_restore_minimized(not test_mode.isChecked())
    test_mode.toggled.connect(_on_test_mode)
    layout.addWidget(test_mode)

    hint = QLabel(
        "When checked, a minimized GSPro is left minimized and club keys are not sent. "
        "Keys still go to GSPro when it is already on screen. Remembered between runs."
    )
    hint.setWordWrap(True)
    layout.addWidget(hint)
    layout.addStretch(1)
    return page


def _on_test_mode(checked: bool) -> None:
    focus.set_restore_minimized(not checked)
    set_bool(TEST_MODE_KEY, checked)
