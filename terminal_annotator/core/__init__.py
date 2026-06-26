"""Terminal-agnostic annotation core."""

from terminal_annotator.core.formatter import format_pending_annotations
from terminal_annotator.core.store import (
    clear_pending_annotations,
    clear_session,
    get_pending_annotations,
    mark_inserted,
    save_annotation,
)

__all__ = [
    "clear_session",
    "clear_pending_annotations",
    "format_pending_annotations",
    "get_pending_annotations",
    "mark_inserted",
    "save_annotation",
]
