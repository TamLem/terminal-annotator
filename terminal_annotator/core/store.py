"""Runtime/cache JSON storage for terminal annotations."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from terminal_annotator.core.annotation import (
    Annotation,
    AnnotationStatus,
    Session,
    json_safe_dict,
    now_iso,
)
from terminal_annotator.core.logging import log_event

APP_DIRNAME = "terminal-annotator"


def storage_root() -> Path:
    xdg_runtime = os.environ.get("XDG_RUNTIME_DIR")
    if xdg_runtime:
        return Path(xdg_runtime) / APP_DIRNAME

    cache_home = os.environ.get("XDG_CACHE_HOME")
    if cache_home:
        return Path(cache_home) / APP_DIRNAME

    home = Path.home()
    if str(home) != "/":
        return home / ".cache" / APP_DIRNAME

    user = os.environ.get("USER") or "unknown"
    return Path("/tmp") / f"{APP_DIRNAME}-{user}"


def sessions_dir() -> Path:
    return storage_root() / "sessions"


def audio_dir() -> Path:
    return storage_root() / "audio"


def logs_dir() -> Path:
    return storage_root() / "logs"


def session_path(session_id: str) -> Path:
    safe_id = "".join(ch for ch in session_id if ch.isalnum() or ch in {"-", "_"})
    if not safe_id:
        raise ValueError("session_id must contain at least one safe character")
    return sessions_dir() / f"{safe_id}.json"


def load_session(session_id: str) -> Session | None:
    path = session_path(session_id)
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as handle:
        return Session.from_dict(json.load(handle))


def save_session(session: Session) -> None:
    directory = sessions_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = session_path(session.session_id)
    session.updated_at = now_iso()
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=directory,
        text=True,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(session.to_dict(), handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        os.replace(tmp_name, path)
    finally:
        tmp_path = Path(tmp_name)
        if tmp_path.exists():
            tmp_path.unlink()


def get_or_create_session(
    session_id: str,
    metadata: dict[str, Any] | None = None,
) -> Session:
    session = load_session(session_id)
    if session is not None:
        return session
    return Session.new(session_id, metadata)


def save_annotation(
    session_id: str,
    selected_text: str,
    comment: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not selected_text:
        raise ValueError("selected_text must not be empty")
    if not comment or not comment.strip():
        raise ValueError("comment must not be empty")

    metadata = json_safe_dict(metadata)
    session = get_or_create_session(session_id, metadata)
    annotation = Annotation(
        selected_text=selected_text,
        comment=comment.strip(),
        metadata={k: v for k, v in metadata.items() if k not in {"terminal", "cwd"}},
    )
    session.annotations.append(annotation)
    save_session(session)
    log_event(
        "annotation_saved",
        session_id=session_id,
        annotation_id=annotation.id,
        selected_text_length=len(selected_text),
        comment_length=len(comment.strip()),
        has_voice=bool(annotation.metadata.get("voice")),
    )
    return annotation.to_dict()


def get_pending_annotations(session_id: str) -> list[dict[str, Any]]:
    session = load_session(session_id)
    if session is None:
        return []
    return [
        annotation.to_dict()
        for annotation in session.annotations
        if annotation.status == AnnotationStatus.PENDING
    ]


def mark_inserted(session_id: str, annotation_ids: list[str]) -> int:
    if not annotation_ids:
        return 0
    session = load_session(session_id)
    if session is None:
        return 0

    target_ids = set(annotation_ids)
    changed = 0
    for annotation in session.annotations:
        if annotation.id in target_ids and annotation.status == AnnotationStatus.PENDING:
            annotation.status = AnnotationStatus.INSERTED
            changed += 1

    if changed:
        save_session(session)
    return changed


def clear_session(session_id: str) -> int:
    session = load_session(session_id)
    if session is None:
        return 0

    changed = 0
    for annotation in session.annotations:
        if annotation.status != AnnotationStatus.CLEARED:
            annotation.status = AnnotationStatus.CLEARED
            changed += 1

    if changed:
        save_session(session)
    return changed


def clear_pending_annotations(session_id: str) -> int:
    session = load_session(session_id)
    if session is None:
        return 0

    changed = 0
    for annotation in session.annotations:
        if annotation.status == AnnotationStatus.PENDING:
            annotation.status = AnnotationStatus.CLEARED
            changed += 1

    if changed:
        save_session(session)
    return changed


def list_sessions() -> list[dict[str, Any]]:
    directory = sessions_dir()
    if not directory.exists():
        return []

    sessions: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.json")):
        try:
            with path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            continue
        annotations = data.get("annotations") or []
        sessions.append(
            {
                "session_id": data.get("session_id") or path.stem,
                "terminal": data.get("terminal"),
                "cwd": data.get("cwd"),
                "updated_at": data.get("updated_at"),
                "annotation_count": len(annotations),
                "pending_count": sum(
                    1 for item in annotations if item.get("status") == "pending"
                ),
            }
        )
    return sessions
