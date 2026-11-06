"""Resource roots for a dev checkout and a PyInstaller onefile build."""

import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False)) and hasattr(sys, "_MEIPASS")


def bundle_root() -> Path:
    """Read-only files shipped with the app (ui, resources)."""
    if is_frozen():
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


def resource_path(*parts: str) -> Path:
    return bundle_root().joinpath(*parts)


def writable_dir() -> Path:
    """Logs and other writable files. Next to the exe when frozen."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent
