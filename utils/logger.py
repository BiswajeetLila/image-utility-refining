import logging
import sys
from datetime import datetime
from pathlib import Path

LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

MAX_LOG_FILES = 10
_existing = sorted(LOG_DIR.glob("session_*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
for old in _existing[MAX_LOG_FILES - 1:]:
    try:
        old.unlink()
    except OSError:
        pass

_log_file = LOG_DIR / f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S")

_file_handler = logging.FileHandler(_log_file, encoding="utf-8")
_file_handler.setFormatter(_formatter)
_file_handler.setLevel(logging.DEBUG)

_console_handler = logging.StreamHandler(sys.stdout)
_console_handler.setFormatter(_formatter)
_console_handler.setLevel(logging.INFO)

_root = logging.getLogger("ImageUtility")
_root.setLevel(logging.DEBUG)
_root.addHandler(_file_handler)
_root.addHandler(_console_handler)


def get_logger(name: str) -> logging.Logger:
    return _root.getChild(name)


def get_log_file() -> Path:
    return _log_file
