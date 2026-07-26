"""Small shared helpers for user-facing pipeline progress."""

import logging
from collections.abc import Callable

ProgressCallback = Callable[[int, str], None]
logger = logging.getLogger(__name__)


def report_progress(callback: ProgressCallback | None, percent: int, message: str) -> None:
    """Send a safe progress update without exposing transcript or note content."""
    percent = max(0, min(100, int(percent)))
    logger.info("Pipeline progress %d%%: %s", percent, message)
    if callback is not None:
        callback(percent, message)
