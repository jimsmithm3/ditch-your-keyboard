"""Start GSPro from a voice command. Starting only: this does not focus GSPro or send keys."""

import logging
import subprocess
import time
from pathlib import Path
from app.grammar_words import NAV

log = logging.getLogger(__name__)

# The same program and working folder as the "GSPro Launcher" shortcut's target.
GSPRO_DIR = Path(r"C:\golfsim\GSProV1")
GSPRO_EXE = GSPRO_DIR / "Core" / "GSPv4" / "GSpro.exe"
# GSPro takes a while to show its window. Don't start a second copy while the first one loads.
STARTING_SECONDS = 90

# The shortcut "SQG-GSPRO-Connect" target and folder. It links the launch monitor to GSPro.
CONNECTOR_DIR = Path(r"C:\Program Files\Invant Inc\SQG-GSPRO-Connect")
CONNECTOR_EXE = CONNECTOR_DIR / "SQG-GSPRO-Connect.exe"

_started_at: float | None = None
_connector_started_at: float | None = None


def _process_running(image: str) -> bool:
    """Check by program name. Window titles are not safe: an Explorer window named
    "SQG-GSPRO-Connect (2) Properties" or "GSPro - File Explorer" would look like the app."""
    try:
        out = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {image}", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        ).stdout
    except (OSError, subprocess.SubprocessError):
        log.exception("could not list processes")
        return False
    return f'"{image}"'.lower() in out.lower()


def _launch(exe: Path, folder: Path, label: str) -> str:
    """Start one program detached from this app. Returns a note, or "" when started."""
    if not exe.is_file():
        log.error("%s not found at %s", label, exe)
        return f"{label} not found at {exe}"
    # Start through "cmd start" so the program is not a child of this app. A child dies when
    # the app is stopped from PyCharm, which takes GSPro down with it. This matches how the
    # shortcut starts a program.
    try:
        subprocess.Popen(
            ["cmd.exe", "/c", "start", "", "/D", str(folder), str(exe)],
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            close_fds=True,
        )
    except OSError as exc:
        log.exception("could not start %s", label)
        return f"could not start {label}: {exc}"
    log.info("started %s from %s", label, exe)
    return ""


def start_gspro() -> str:
    """Start GSPro if it is not running. Returns a short note for the status bar."""
    global _started_at
    from app.gspro_sequences import mark_running, set_screen

    if _process_running("GSpro.exe"):
        mark_running()
        return "GSPro is already running"
    if _started_at is not None and time.monotonic() - _started_at < STARTING_SECONDS:
        return "GSPro is still starting"
    note = _launch(GSPRO_EXE, GSPRO_DIR, "GSPro")
    if note:
        return note
    _started_at = time.monotonic()
    set_screen("home")  # a fresh start opens on the home screen
    return "Starting GSPro."


def start_connector() -> str:
    """Start SQG-GSPRO-Connect if it is not running. Returns a short note."""
    global _connector_started_at
    if _process_running("SQG-GSPRO-Connect.exe"):
        return "SQG-GSPRO-Connect is already running"
    if _connector_started_at is not None and time.monotonic() - _connector_started_at < STARTING_SECONDS:
        return "SQG-GSPRO-Connect is still starting"
    note = _launch(CONNECTOR_EXE, CONNECTOR_DIR, "SQG-GSPRO-Connect")
    if note:
        return note
    _connector_started_at = time.monotonic()
    return "Starting SQG-GSPRO-Connect."


def stop_connector() -> str:
    """Close SQG-GSPRO-Connect by program name. Returns a short note."""
    if not _process_running("SQG-GSPRO-Connect.exe"):
        return "SQG-GSPRO-Connect is not running"
    try:
        result = subprocess.run(
            ["taskkill", "/IM", "SQG-GSPRO-Connect.exe", "/T", "/F"],
            capture_output=True,
            text=True,
            timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError):
        log.exception("could not run taskkill for the connector")
        return "could not close SQG-GSPRO-Connect"
    if result.returncode != 0:
        log.warning("taskkill for the connector failed: %s", result.stderr.strip() or result.stdout.strip())
        return "could not close SQG-GSPRO-Connect"
    log.info("closed SQG-GSPRO-Connect")
    global _connector_started_at
    _connector_started_at = None
    return "Closed SQG-GSPRO-Connect."


def start_play_golf(on_done=None) -> str:
    """The "start gspro" command: start GSPro and the connector, then click the connector's
    Scan / Connect buttons in the background. on_done(note) reports the setup result."""
    from app.connector_ui import finish_setup_in_background

    note = "; ".join(part for part in (start_gspro(), start_connector()) if part)
    finish_setup_in_background(on_done)
    return note
