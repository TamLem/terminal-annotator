from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from terminal_annotator.adapters.transcription.litellm_provider import transcribe_audio
from terminal_annotator.core.transcription import (
    TranscriptionConfig,
    TranscriptionError,
)


class FakeTranscriptionResponse:
    text = "transcribed note"
    duration = 1.25
    _hidden_params = {"custom_llm_provider": "openai"}

    def model_dump(self) -> dict[str, str]:
        return {"text": self.text}


class LiteLLMProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.audio_path = Path(self.tempdir.name) / "note.wav"
        self.audio_path.write_bytes(b"fake wav")

    def test_transcribes_with_file_tuple_and_proxy_config(self) -> None:
        calls: list[dict] = []

        def fake_transcription(**kwargs):
            calls.append(kwargs)
            return FakeTranscriptionResponse()

        fake_litellm = types.SimpleNamespace(transcription=fake_transcription)
        config = TranscriptionConfig(
            model="openai/whisper-1",
            base_url="http://127.0.0.1:4000",
            api_key="proxy-key",
        )

        with patch.dict(sys.modules, {"litellm": fake_litellm}):
            result = transcribe_audio(self.audio_path, config)

        self.assertEqual(result.text, "transcribed note")
        self.assertEqual(result.provider, "litellm")
        self.assertEqual(result.model, "openai/whisper-1")
        self.assertEqual(result.duration_seconds, 1.25)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["model"], "openai/whisper-1")
        self.assertEqual(calls[0]["file"], ("note.wav", b"fake wav", "audio/wav"))
        self.assertEqual(calls[0]["api_base"], "http://127.0.0.1:4000")
        self.assertEqual(calls[0]["api_key"], "proxy-key")
        self.assertTrue(calls[0]["drop_params"])

    def test_falls_back_to_next_model(self) -> None:
        calls: list[str] = []

        def fake_transcription(**kwargs):
            calls.append(kwargs["model"])
            if kwargs["model"] == "bad/model":
                raise RuntimeError("provider failed")
            return {"text": "fallback transcript", "duration": 2}

        fake_litellm = types.SimpleNamespace(transcription=fake_transcription)
        config = TranscriptionConfig(
            model="bad/model",
            fallbacks=["openai/whisper-1"],
        )

        with patch.dict(sys.modules, {"litellm": fake_litellm}):
            result = transcribe_audio(self.audio_path, config)

        self.assertEqual(calls, ["bad/model", "openai/whisper-1"])
        self.assertEqual(result.text, "fallback transcript")
        self.assertEqual(result.model, "openai/whisper-1")

    def test_missing_litellm_has_readable_error(self) -> None:
        with patch.dict(sys.modules, {"litellm": None}):
            with self.assertRaisesRegex(TranscriptionError, "LiteLLM is not installed"):
                transcribe_audio(self.audio_path, TranscriptionConfig())


if __name__ == "__main__":
    unittest.main()
