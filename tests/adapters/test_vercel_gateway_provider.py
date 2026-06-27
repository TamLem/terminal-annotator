from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from terminal_annotator.adapters.transcription.vercel_gateway_provider import (
    _optimized_upload_path,
    transcribe_audio,
)
from terminal_annotator.core.transcription import (
    TranscriptionConfig,
    TranscriptionError,
)


class FakeHTTPResponse:
    def __init__(self, data: dict[str, str]):
        self.data = json.dumps(data).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self) -> bytes:
        return self.data


class VercelGatewayProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.audio_path = Path(self.tempdir.name) / "note.wav"
        self.audio_path.write_bytes(b"fake wav")

    def test_posts_base64_audio_to_vercel_gateway(self) -> None:
        captured = {}

        def fake_urlopen(request, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return FakeHTTPResponse({"text": "hello transcript"})

        config = TranscriptionConfig(
            provider="vercel-ai-gateway",
            model="openai/whisper-1",
            api_key="vercel-key",
        )

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            result = transcribe_audio(self.audio_path, config)

        request = captured["request"]
        body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(result.text, "hello transcript")
        self.assertEqual(result.provider, "vercel-ai-gateway")
        self.assertEqual(result.model, "openai/whisper-1")
        self.assertEqual(captured["timeout"], 60)
        self.assertEqual(request.headers["Authorization"], "Bearer vercel-key")
        self.assertEqual(request.headers["Ai-model-id"], "openai/whisper-1")
        self.assertEqual(request.headers["Ai-gateway-auth-method"], "api-key")
        self.assertEqual(request.headers["Ai-gateway-protocol-version"], "0.0.1")
        self.assertEqual(
            request.headers["Ai-transcription-model-specification-version"],
            "4",
        )
        self.assertEqual(body["audio"], "ZmFrZSB3YXY=")
        self.assertEqual(body["mediaType"], "audio/wav")

    def test_missing_api_key_has_readable_error(self) -> None:
        config = TranscriptionConfig(
            provider="vercel-ai-gateway",
            model="openai/whisper-1",
            api_key_env="AI_GATEWAY_API_KEY",
        )

        with self.assertRaisesRegex(TranscriptionError, "AI_GATEWAY_API_KEY"):
            transcribe_audio(self.audio_path, config)

    def test_optimizes_wav_to_mp3_when_ffmpeg_exists(self) -> None:
        mp3_path = self.audio_path.with_suffix(".mp3")

        def fake_run(command, check, stdout, stderr):
            self.assertEqual(command[0], "ffmpeg")
            self.assertIn("-b:a", command)
            mp3_path.write_bytes(b"mp3")

        with patch("shutil.which", return_value="/usr/bin/ffmpeg"), patch(
            "subprocess.run",
            side_effect=fake_run,
        ):
            upload_path = _optimized_upload_path(self.audio_path)

        self.assertEqual(upload_path, mp3_path)

    def test_uses_original_audio_when_ffmpeg_missing(self) -> None:
        with patch("shutil.which", return_value=None):
            upload_path = _optimized_upload_path(self.audio_path)

        self.assertEqual(upload_path, self.audio_path)


if __name__ == "__main__":
    unittest.main()
