"""Developer page: switches for testing gspraudio without disturbing GSPro."""

from PySide6.QtWidgets import QCheckBox, QLabel, QVBoxLayout, QWidget

from app import focus
from app.prefs import get_bool, get_pref, set_bool, set_pref

TEST_MODE_KEY = "test_mode"
SEND_KEYS_KEY = "send_keys_default"  # same key as the Preferences row "Send Keys At Start"


def build_developer_page() -> QWidget:
    page = QWidget()
    layout = QVBoxLayout(page)

    # Keys go to GSPro by default. Turn this off only to test without sending keys.
    send_keys = QCheckBox("Send keys to GSPro")
    send_keys.setChecked(get_pref(SEND_KEYS_KEY, "True") == "True")
    send_keys.toggled.connect(lambda checked: set_pref(SEND_KEYS_KEY, "True" if checked else "False"))
    page.send_keys_check = send_keys  # main_window.py connects this to the listener
    layout.addWidget(send_keys)

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
