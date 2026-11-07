"""File logging. Windowed exe has no console, so this is the crash trail."""

import logging
from pathlib import Path

from app.paths import writable_dir


def setup_logging() -> Path:
    log_dir = writable_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "gspraudio.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[logging.FileHandler(log_file, encoding="utf-8")],
    )
    logging.getLogger(__name__).info("log file %s", log_file)
    return log_file
