"""Which game plug-in is active. Only one is active at a time; the overview page's Game dropdown picks it and the
choice is saved in the app's settings. A switch takes effect after a restart.

A first run has no game chosen (none). A user who already has players has been using GSPro, so that stays the
default for them. Choosing GSPro on a first run then asks for the player's name and bag, as before."""

from app.players import list_players
from app.prefs import get_pref, set_pref

PLUGIN_PREF = "active_plugin"
NONE = "none"  # the saved value for "no game chosen"
AVAILABLE: tuple[str, ...] = ("GSPro",)  # the plug-ins that exist; a new one is added here when it is written


def active() -> str:
    """The chosen game, or "" for none."""
    saved = get_pref(PLUGIN_PREF, "")
    if saved in AVAILABLE:
        return saved
    if saved == NONE:
        return ""
    # Never chosen: someone with players already has been using GSPro, so keep that. A new install starts with none.
    return AVAILABLE[0] if list_players() else ""


def set_active(name: str) -> None:
    """Save the choice: a plug-in name in AVAILABLE, or "" for none."""
    if name in AVAILABLE:
        set_pref(PLUGIN_PREF, name)
    elif name == "":
        set_pref(PLUGIN_PREF, NONE)
