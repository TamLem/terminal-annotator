"""Format pending terminal comments into terminal input text."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from terminal_annotator.core.store import get_pending_annotations

DEFAULT_PREVIEW_LIMIT = 1200
VALID_MODES = {"ai-review", "plain-notes", "compact"}


def _preview(text: str, limit: int = DEFAULT_PREVIEW_LIMIT) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}\n...[truncated]"


def format_annotations(
    annotations: Iterable[dict[str, Any]],
    mode: str = "ai-review",
) -> str:
    annotations = list(annotations)
    if not annotations:
        return ""
    if mode not in VALID_MODES:
        raise ValueError(f"unknown formatter mode: {mode}")

    if mode == "compact":
        lines = ["Review notes:"]
        for index, annotation in enumerate(annotations, start=1):
            selected = _preview(str(annotation.get("selected_text", "")), 300)
            comment = str(annotation.get("comment", "")).strip()
            if selected:
                lines.append(f"{index}. {selected} -> {comment}")
            else:
                lines.append(f"{index}. {comment}")
        return "\n".join(lines)

    if mode == "plain-notes":
        header = "Review terminal comments:"
        selected_label = "Context:"
        comment_label = "Comment:"
        footer = ""
    else:
        header = "Apply these terminal comments:"
        selected_label = "Context:"
        comment_label = "My comment:"
        footer = "Address these comments before continuing."

    lines = [header, ""]
    for index, annotation in enumerate(annotations, start=1):
        selected = _preview(str(annotation.get("selected_text", "")))
        comment = str(annotation.get("comment", "")).strip()
        if selected:
            lines.extend(
                [
                    f"{index}. {selected_label}",
                    f'"{selected}"',
                    "",
                    comment_label,
                    comment,
                    "",
                ]
            )
        else:
            lines.extend(
                [
                    f"{index}. Terminal comment:",
                    comment,
                    "",
                ]
            )

    if footer:
        lines.append(footer)
    return "\n".join(lines).rstrip() + "\n"


def format_pending_annotations(session_id: str, mode: str = "ai-review") -> str:
    return format_annotations(get_pending_annotations(session_id), mode=mode)
