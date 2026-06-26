"""Annotation data structures and JSON conversion helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from collections.abc import Mapping, Sequence
from typing import Any
from uuid import uuid4


class AnnotationStatus(str, Enum):
    PENDING = "pending"
    INSERTED = "inserted"
    CLEARED = "cleared"


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [json_safe(item) for item in value]
    return str(value)


def json_safe_dict(data: dict[str, Any] | None) -> dict[str, Any]:
    return json_safe(dict(data or {}))


@dataclass(slots=True)
class Annotation:
    selected_text: str
    comment: str
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    status: AnnotationStatus = AnnotationStatus.PENDING
    created_at: str = field(default_factory=now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Annotation":
        return cls(
            id=str(data["id"]),
            selected_text=str(data.get("selected_text", "")),
            comment=str(data.get("comment", "")),
            status=AnnotationStatus(str(data.get("status", AnnotationStatus.PENDING))),
            created_at=str(data.get("created_at") or now_iso()),
            metadata=json_safe_dict(data.get("metadata")),
        )

    def to_dict(self) -> dict[str, Any]:
        data = {
            "id": self.id,
            "selected_text": self.selected_text,
            "comment": self.comment,
            "status": self.status.value,
            "created_at": self.created_at,
        }
        if self.metadata:
            data["metadata"] = self.metadata
        return data


@dataclass(slots=True)
class Session:
    session_id: str
    terminal: str | None = None
    cwd: str | None = None
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)
    annotations: list[Annotation] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def new(cls, session_id: str, metadata: dict[str, Any] | None = None) -> "Session":
        metadata = json_safe_dict(metadata)
        return cls(
            session_id=session_id,
            terminal=metadata.get("terminal"),
            cwd=metadata.get("cwd"),
            metadata={k: v for k, v in metadata.items() if k not in {"terminal", "cwd"}},
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Session":
        metadata = json_safe_dict(data.get("metadata"))
        return cls(
            session_id=str(data["session_id"]),
            terminal=data.get("terminal"),
            cwd=data.get("cwd"),
            created_at=str(data.get("created_at") or now_iso()),
            updated_at=str(data.get("updated_at") or now_iso()),
            annotations=[
                Annotation.from_dict(item)
                for item in data.get("annotations", [])
                if isinstance(item, dict)
            ],
            metadata=metadata,
        )

    def to_dict(self) -> dict[str, Any]:
        data = {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "annotations": [annotation.to_dict() for annotation in self.annotations],
        }
        if self.terminal:
            data["terminal"] = self.terminal
        if self.cwd:
            data["cwd"] = self.cwd
        if self.metadata:
            data["metadata"] = self.metadata
        return data
