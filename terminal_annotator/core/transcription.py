"""Terminal-agnostic transcription data structures and configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from terminal_annotator.core.annotation import json_safe_dict

DEFAULT_TRANSCRIPTION_PROVIDER = "litellm"
DEFAULT_TRANSCRIPTION_MODEL = "openai/whisper-1"


class TranscriptionError(RuntimeError):
    """Raised when audio transcription cannot be completed."""


@dataclass(slots=True)
class TranscriptionConfig:
    provider: str = DEFAULT_TRANSCRIPTION_PROVIDER
    model: str = DEFAULT_TRANSCRIPTION_MODEL
    fallbacks: list[str] = field(default_factory=list)
    base_url: str | None = None
    api_key: str | None = None

    @property
    def model_chain(self) -> list[str]:
        seen: set[str] = set()
        models: list[str] = []
        for model in [self.model, *self.fallbacks]:
            model = model.strip()
            if model and model not in seen:
                seen.add(model)
                models.append(model)
        return models


@dataclass(slots=True)
class TranscriptionResult:
    text: str
    provider: str
    model: str
    audio_path: str
    duration_seconds: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_metadata(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "audio_path": self.audio_path,
            "provider": self.provider,
            "model": self.model,
        }
        if self.duration_seconds is not None:
            data["duration_seconds"] = self.duration_seconds
        if self.metadata:
            data["response"] = json_safe_dict(self.metadata)
        return data


def transcription_config_from_env(
    env: dict[str, str] | None = None,
) -> TranscriptionConfig:
    source = env if env is not None else os.environ
    provider = source.get(
        "TERMINAL_ANNOTATOR_TRANSCRIBE_PROVIDER",
        DEFAULT_TRANSCRIPTION_PROVIDER,
    ).strip() or DEFAULT_TRANSCRIPTION_PROVIDER
    model = source.get(
        "TERMINAL_ANNOTATOR_TRANSCRIBE_MODEL",
        DEFAULT_TRANSCRIPTION_MODEL,
    ).strip() or DEFAULT_TRANSCRIPTION_MODEL
    fallbacks = _split_csv(source.get("TERMINAL_ANNOTATOR_TRANSCRIBE_FALLBACKS", ""))
    return TranscriptionConfig(
        provider=provider,
        model=model,
        fallbacks=fallbacks,
        base_url=_empty_to_none(source.get("TERMINAL_ANNOTATOR_LITELLM_BASE_URL")),
        api_key=_empty_to_none(source.get("TERMINAL_ANNOTATOR_LITELLM_API_KEY")),
    )


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _empty_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None
