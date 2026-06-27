"""LiteLLM transcription provider."""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any

from terminal_annotator.core.annotation import json_safe_dict
from terminal_annotator.core.transcription import (
    TranscriptionConfig,
    TranscriptionError,
    TranscriptionResult,
)


def transcribe_audio(
    audio_path: Path,
    config: TranscriptionConfig,
) -> TranscriptionResult:
    if config.provider != "litellm":
        raise TranscriptionError(f"unsupported transcription provider: {config.provider}")

    try:
        import litellm
    except ImportError as exc:
        raise TranscriptionError(
            "LiteLLM is not installed. Install the voice extra to enable transcription."
        ) from exc

    if not audio_path.exists():
        raise TranscriptionError(f"audio file does not exist: {audio_path}")
    if not audio_path.is_file():
        raise TranscriptionError(f"audio path is not a file: {audio_path}")

    audio_bytes = audio_path.read_bytes()
    content_type = _content_type(audio_path)
    file_upload = (audio_path.name, audio_bytes, content_type)
    errors: list[str] = []

    for model in config.model_chain:
        try:
            response = litellm.transcription(
                **_request_kwargs(
                    model=model,
                    file_upload=file_upload,
                    config=config,
                )
            )
            text = _response_text(response)
            if not text:
                raise TranscriptionError("provider returned an empty transcript")
            return TranscriptionResult(
                text=text,
                provider="litellm",
                model=model,
                audio_path=str(audio_path),
                duration_seconds=_response_duration(response),
                metadata=_response_metadata(response),
            )
        except Exception as exc:  # noqa: BLE001 - provider errors vary by backend.
            errors.append(f"{model}: {exc}")

    raise TranscriptionError("LiteLLM transcription failed: " + "; ".join(errors))


def _request_kwargs(
    model: str,
    file_upload: tuple[str, bytes, str],
    config: TranscriptionConfig,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "model": model,
        "file": file_upload,
        "response_format": "json",
        "drop_params": True,
    }
    if config.base_url:
        kwargs["api_base"] = config.base_url
    if config.api_key:
        kwargs["api_key"] = config.api_key
    return kwargs


def _content_type(audio_path: Path) -> str:
    content_type = mimetypes.guess_type(audio_path.name)[0] or "audio/wav"
    if content_type == "audio/x-wav":
        return "audio/wav"
    return content_type


def _response_text(response: Any) -> str:
    text = getattr(response, "text", None)
    if text is None and isinstance(response, dict):
        text = response.get("text")
    return str(text or "").strip()


def _response_duration(response: Any) -> float | None:
    duration = getattr(response, "duration", None)
    if duration is None and isinstance(response, dict):
        duration = response.get("duration")
    if duration is None:
        return None
    try:
        return float(duration)
    except (TypeError, ValueError):
        return None


def _response_metadata(response: Any) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    hidden = getattr(response, "_hidden_params", None)
    if isinstance(hidden, dict):
        metadata["hidden_params"] = hidden
    if hasattr(response, "model_dump"):
        try:
            dumped = response.model_dump()
        except Exception:  # noqa: BLE001 - defensive around provider response types.
            dumped = None
        if isinstance(dumped, dict):
            metadata["response"] = dumped
    elif isinstance(response, dict):
        metadata["response"] = response
    return json_safe_dict(metadata)
