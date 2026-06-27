"""Vercel AI Gateway transcription provider."""

from __future__ import annotations

import base64
import json
import mimetypes
import shutil
import subprocess
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
    upload_path = _optimized_upload_path(audio_path)
    log_event(
        "transcription_request_started",
        provider="vercel-ai-gateway",
        model=config.model,
        url=url,
        audio_path=str(audio_path),
        upload_path=str(upload_path),
        upload_bytes=upload_path.stat().st_size if upload_path.exists() else None,
    )
    response = _post_transcription(
        url=url,
        api_key=config.api_key,
        model=config.model,
        audio_path=upload_path,
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
        metadata={
            "upload_path": str(upload_path),
            "upload_media_type": _content_type(upload_path),
            "response": response,
        },
    )


def _optimized_upload_path(audio_path: Path) -> Path:
    if audio_path.suffix.lower() == ".mp3":
        return audio_path
    if not shutil.which("ffmpeg"):
        log_event(
            "transcription_audio_optimization_skipped",
            provider="vercel-ai-gateway",
            reason="ffmpeg not found",
            audio_path=str(audio_path),
        )
        return audio_path

    target = audio_path.with_suffix(".mp3")
    command = [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-i",
        str(audio_path),
        "-ac",
        "1",
        "-ar",
        "16000",
        "-b:a",
        "32k",
        str(target),
    ]
    try:
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    except (OSError, subprocess.CalledProcessError) as exc:
        log_event(
            "transcription_audio_optimization_failed",
            provider="vercel-ai-gateway",
            error=str(exc),
            audio_path=str(audio_path),
        )
        return audio_path

    if not target.exists() or target.stat().st_size <= 0:
        log_event(
            "transcription_audio_optimization_failed",
            provider="vercel-ai-gateway",
            error="empty optimized file",
            audio_path=str(audio_path),
        )
        return audio_path

    log_event(
        "transcription_audio_optimized",
        provider="vercel-ai-gateway",
        audio_path=str(audio_path),
        upload_path=str(target),
        original_bytes=audio_path.stat().st_size,
        upload_bytes=target.stat().st_size,
    )
    return target


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
