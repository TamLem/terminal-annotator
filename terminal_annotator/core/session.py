"""Session identity helpers."""

from __future__ import annotations

from hashlib import sha256
from typing import Any


def _short_hash(parts: list[str]) -> str:
    payload = "\0".join(parts).encode("utf-8", errors="replace")
    return sha256(payload).hexdigest()[:12]


def generate_session_id(identity: dict[str, Any]) -> str:
    terminal_uuid = identity.get("terminal_uuid")
    child_pid = identity.get("child_pid")
    cwd = identity.get("cwd")
    if terminal_uuid and child_pid and cwd:
        return _short_hash([str(terminal_uuid), str(child_pid), str(cwd)])

    window_id = identity.get("window_id")
    pane_pid = identity.get("pane_pid")
    if window_id and pane_pid and cwd:
        return _short_hash([str(window_id), str(pane_pid), str(cwd)])

    created_timestamp = identity.get("created_timestamp")
    if child_pid and cwd and created_timestamp:
        return _short_hash([str(child_pid), str(cwd), str(created_timestamp)])

    if child_pid and cwd:
        return _short_hash([str(child_pid), str(cwd)])

    available = [
        str(identity[key])
        for key in sorted(identity)
        if identity.get(key) not in {None, ""}
    ]
    if not available:
        raise ValueError("cannot generate session_id from empty identity")
    return _short_hash(available)


def session_metadata(identity: dict[str, Any]) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    for key in (
        "terminal",
        "cwd",
        "terminal_uuid",
        "window_id",
        "child_pid",
        "pane_pid",
        "created_timestamp",
    ):
        value = identity.get(key)
        if value not in {None, ""}:
            metadata[key] = value
    return metadata
