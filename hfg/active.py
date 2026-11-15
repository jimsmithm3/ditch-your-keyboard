"""Which game plug-in is active. Only one is active at a time; the overview page's Game dropdown picks it and the
choice is saved in the app's settings. A switch takes effect after a restart."""

from app.prefs import get_pref, set_pref

PLUGIN_PREF = "active_plugin"
AVAILABLE: tuple[str, ...] = ("GSPro",)  # the plug-ins that exist; a new one is added here when it is written
DEFAULT = "GSPro"


def active() -> str:
    name = get_pref(PLUGIN_PREF, DEFAULT)
    return name if name in AVAILABLE else DEFAULT


def set_active(name: str) -> None:
    if name in AVAILABLE:
        set_pref(PLUGIN_PREF, name)
