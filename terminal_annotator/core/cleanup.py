"""Cleanup helpers for old annotation sessions."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from terminal_annotator.core.store import audio_dir, sessions_dir


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def cleanup_old_sessions(max_age_days: int = 7) -> int:
    directory = sessions_dir()
    if not directory.exists():
        return 0

    cutoff = datetime.now().astimezone() - timedelta(days=max_age_days)
    removed = 0
    for path in directory.glob("*.json"):
        timestamp = _session_timestamp(path)
        if timestamp < cutoff:
            _remove_referenced_audio(path)
            path.unlink()
            removed += 1
    return removed


def _session_timestamp(path: Path) -> datetime:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        parsed = _parse_timestamp(data.get("updated_at"))
        if parsed is not None:
            return parsed.astimezone()
    except (OSError, json.JSONDecodeError, AttributeError):
        pass
    return datetime.fromtimestamp(path.stat().st_mtime).astimezone()


def _remove_referenced_audio(session_path: Path) -> None:
    try:
        data = json.loads(session_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return

    for annotation in data.get("annotations", []):
        if not isinstance(annotation, dict):
            continue
        metadata = annotation.get("metadata")
        if not isinstance(metadata, dict):
            continue
        voice = metadata.get("voice")
        if not isinstance(voice, dict):
            continue
        audio_path = voice.get("audio_path")
        if isinstance(audio_path, str):
            _remove_audio_path(audio_path)


def _remove_audio_path(value: str) -> None:
    try:
        path = Path(value).expanduser().resolve()
        root = audio_dir().resolve()
        path.relative_to(root)
    except (OSError, ValueError):
        return

    try:
        if path.is_file():
            path.unlink()
    except OSError:
        return
