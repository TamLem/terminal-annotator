"""Transcription provider adapters."""

from __future__ import annotations

from pathlib import Path

from terminal_annotator.core.transcription import (
    TranscriptionConfig,
    TranscriptionError,
    TranscriptionResult,
)


def transcribe_audio(
    audio_path: Path,
    config: TranscriptionConfig,
) -> TranscriptionResult:
    if config.provider == "litellm":
        from terminal_annotator.adapters.transcription.litellm_provider import (
            transcribe_audio as transcribe_litellm,
        )

        return transcribe_litellm(audio_path, config)

    if config.provider == "vercel-ai-gateway":
        from terminal_annotator.adapters.transcription.vercel_gateway_provider import (
            transcribe_audio as transcribe_vercel_gateway,
        )

        return transcribe_vercel_gateway(audio_path, config)

    raise TranscriptionError(f"unsupported transcription provider: {config.provider}")
