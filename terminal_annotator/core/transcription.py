"""Terminal-agnostic transcription data structures and configuration."""

from __future__ import annotations

import os
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from terminal_annotator.core.annotation import json_safe_dict

DEFAULT_TRANSCRIPTION_PROVIDER = "litellm"
DEFAULT_TRANSCRIPTION_MODEL = "openai/whisper-1"
CONFIG_DIRNAME = "terminal-annotator"
CONFIG_FILENAME = "config.json"


class TranscriptionError(RuntimeError):
    """Raised when audio transcription cannot be completed."""


@dataclass(slots=True)
class TranscriptionConfig:
    provider: str = DEFAULT_TRANSCRIPTION_PROVIDER
    model: str = DEFAULT_TRANSCRIPTION_MODEL
    fallbacks: list[str] = field(default_factory=list)
    base_url: str | None = None
    api_key: str | None = None
    api_key_env: str | None = None

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


def config_root(env: dict[str, str] | None = None) -> Path:
    source = env if env is not None else os.environ
    config_home = source.get("XDG_CONFIG_HOME")
    if config_home:
        return Path(config_home) / CONFIG_DIRNAME
    return Path.home() / ".config" / CONFIG_DIRNAME


def config_path(env: dict[str, str] | None = None) -> Path:
    return config_root(env) / CONFIG_FILENAME


def transcription_config_from_env(
    env: dict[str, str] | None = None,
    path: Path | None = None,
) -> TranscriptionConfig:
    source = env if env is not None else os.environ
    voice_config = _read_voice_config(path if path is not None else config_path(source))
    provider = source.get(
        "TERMINAL_ANNOTATOR_TRANSCRIBE_PROVIDER",
        str(voice_config.get("provider") or DEFAULT_TRANSCRIPTION_PROVIDER),
    ).strip() or DEFAULT_TRANSCRIPTION_PROVIDER
    model = source.get(
        "TERMINAL_ANNOTATOR_TRANSCRIBE_MODEL",
        str(voice_config.get("model") or DEFAULT_TRANSCRIPTION_MODEL),
    ).strip() or DEFAULT_TRANSCRIPTION_MODEL
    fallbacks = _fallbacks_from_config(voice_config)
    fallback_override = source.get("TERMINAL_ANNOTATOR_TRANSCRIBE_FALLBACKS")
    if fallback_override is not None:
        fallbacks = _split_csv(fallback_override)
    api_key_env = _empty_to_none(str(voice_config.get("api_key_env") or ""))
    return TranscriptionConfig(
        provider=provider,
        model=model,
        fallbacks=fallbacks,
        base_url=(
            _empty_to_none(source.get("TERMINAL_ANNOTATOR_LITELLM_BASE_URL"))
            or _empty_to_none(str(voice_config.get("base_url") or ""))
        ),
        api_key=(
            _empty_to_none(source.get("TERMINAL_ANNOTATOR_LITELLM_API_KEY"))
            or _empty_to_none(str(voice_config.get("api_key") or ""))
            or _key_from_named_env(source, api_key_env)
        ),
        api_key_env=api_key_env,
    )


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _empty_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _read_voice_config(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    voice = data.get("voice")
    return voice if isinstance(voice, dict) else {}


def _fallbacks_from_config(data: dict[str, Any]) -> list[str]:
    value = data.get("fallbacks")
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return _split_csv(value)
    return []


def _key_from_named_env(source: dict[str, str], name: str | None) -> str | None:
    if not name:
        return None
    return _empty_to_none(source.get(name))
