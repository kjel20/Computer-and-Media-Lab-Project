"""Central logging setup for AI Lecture Companion.

Logs operational metadata only. Transcript text, note contents, prompts, and
model responses must never be written to the log.
"""

import logging
from logging.handlers import RotatingFileHandler

from config import LOG_FILE, LOG_FORMAT, LOG_LEVEL, LOG_MAX_BYTES, LOG_BACKUP_COUNT

_CONFIGURED = False


def setup_logging() -> None:
    """Configure console and rotating-file logging once per process."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    level = getattr(logging, str(LOG_LEVEL).upper(), logging.INFO)
    formatter = logging.Formatter(LOG_FORMAT)
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()

    console = logging.StreamHandler()
    console.setLevel(level)
    console.setFormatter(formatter)
    root.addHandler(console)

    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    # Keep third-party HTTP/model libraries from flooding the application log.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("sentence_transformers").setLevel(logging.WARNING)

    _CONFIGURED = True
    logging.getLogger(__name__).info("Application logging configured.")
