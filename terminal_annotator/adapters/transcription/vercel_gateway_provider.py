"""Vercel AI Gateway transcription provider."""

from __future__ import annotations

import base64
import json
import mimetypes
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from terminal_annotator.core.annotation import json_safe_dict
from terminal_annotator.core.logging import log_event
from terminal_annotator.core.transcription import (
    DEFAULT_VERCEL_GATEWAY_URL,
    TranscriptionConfig,
    TranscriptionError,
    TranscriptionResult,
)


def transcribe_audio(
    audio_path: Path,
    config: TranscriptionConfig,
) -> TranscriptionResult:
    if config.provider != "vercel-ai-gateway":
        raise TranscriptionError(f"unsupported transcription provider: {config.provider}")
    if not config.api_key:
        key_hint = f" in {config.api_key_env}" if config.api_key_env else ""
        log_event(
            "transcription_request_missing_key",
            provider="vercel-ai-gateway",
            model=config.model,
            api_key_env=config.api_key_env,
        )
        raise TranscriptionError(f"missing Vercel AI Gateway API key{key_hint}")
    if not audio_path.exists():
        raise TranscriptionError(f"audio file does not exist: {audio_path}")
    if not audio_path.is_file():
        raise TranscriptionError(f"audio path is not a file: {audio_path}")

    url = config.base_url or DEFAULT_VERCEL_GATEWAY_URL
    log_event(
        "transcription_request_started",
        provider="vercel-ai-gateway",
        model=config.model,
        url=url,
        audio_path=str(audio_path),
    )
    response = _post_transcription(
        url=url,
        api_key=config.api_key,
        model=config.model,
        audio_path=audio_path,
    )
    text = _response_text(response)
    if not text:
        log_event(
            "transcription_request_failed",
            provider="vercel-ai-gateway",
            model=config.model,
            error="empty transcript",
        )
        raise TranscriptionError("Vercel AI Gateway returned an empty transcript")
    log_event(
        "transcription_request_succeeded",
        provider="vercel-ai-gateway",
        model=config.model,
        text_length=len(text),
    )
    return TranscriptionResult(
        text=text,
        provider="vercel-ai-gateway",
        model=config.model,
        audio_path=str(audio_path),
        metadata=response,
    )


def _post_transcription(
    url: str,
    api_key: str,
    model: str,
    audio_path: Path,
) -> dict[str, Any]:
    body = {
        "audio": base64.b64encode(audio_path.read_bytes()).decode("ascii"),
        "mediaType": _content_type(audio_path),
    }
    request = urllib.request.Request(
        url=url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "ai-gateway-auth-method": "api-key",
            "ai-gateway-protocol-version": "0.0.1",
            "ai-model-id": model,
            "ai-transcription-model-specification-version": "4",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        log_event(
            "transcription_http_failed",
            provider="vercel-ai-gateway",
            status=exc.code,
            response=details,
        )
        raise TranscriptionError(
            f"Vercel AI Gateway request failed with HTTP {exc.code}: {details}"
        ) from exc
    except urllib.error.URLError as exc:
        log_event(
            "transcription_http_failed",
            provider="vercel-ai-gateway",
            error=str(exc.reason),
        )
        raise TranscriptionError(f"Vercel AI Gateway request failed: {exc.reason}") from exc

    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise TranscriptionError("Vercel AI Gateway returned invalid JSON") from exc
    if not isinstance(data, dict):
        raise TranscriptionError("Vercel AI Gateway returned an unexpected response")
    return json_safe_dict(data)


def _content_type(audio_path: Path) -> str:
    content_type = mimetypes.guess_type(audio_path.name)[0] or "audio/wav"
    if content_type == "audio/x-wav":
        return "audio/wav"
    return content_type


def _response_text(response: dict[str, Any]) -> str:
    for key in ("text", "transcript", "transcription"):
        value = response.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""
