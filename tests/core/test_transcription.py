from __future__ import annotations

import unittest
import tempfile
from pathlib import Path

from terminal_annotator.core.transcription import transcription_config_from_env


class TranscriptionConfigTests(unittest.TestCase):
    def test_defaults_to_litellm_whisper(self) -> None:
        config = transcription_config_from_env({}, path=Path("/tmp/missing-config.json"))

        self.assertEqual(config.provider, "litellm")
        self.assertEqual(config.model, "openai/whisper-1")
        self.assertEqual(config.fallbacks, [])
        self.assertEqual(config.model_chain, ["openai/whisper-1"])

    def test_parses_fallbacks_and_proxy_settings(self) -> None:
        config = transcription_config_from_env(
            {
                "TERMINAL_ANNOTATOR_TRANSCRIBE_PROVIDER": "litellm",
                "TERMINAL_ANNOTATOR_TRANSCRIBE_MODEL": "groq/whisper-large-v3",
                "TERMINAL_ANNOTATOR_TRANSCRIBE_FALLBACKS": (
                    "openai/whisper-1, groq/whisper-large-v3, deepgram/nova-2"
                ),
                "TERMINAL_ANNOTATOR_LITELLM_BASE_URL": "http://127.0.0.1:4000",
                "TERMINAL_ANNOTATOR_LITELLM_API_KEY": "proxy-key",
            },
            path=Path("/tmp/missing-config.json"),
        )

        self.assertEqual(config.provider, "litellm")
        self.assertEqual(config.model, "groq/whisper-large-v3")
        self.assertEqual(
            config.model_chain,
            ["groq/whisper-large-v3", "openai/whisper-1", "deepgram/nova-2"],
        )
        self.assertEqual(config.base_url, "http://127.0.0.1:4000")
        self.assertEqual(config.api_key, "proxy-key")

    def test_reads_file_config_without_shell_exports(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "config.json"
            path.write_text(
                """{
  "voice": {
    "provider": "litellm",
    "model": "openai/gpt-4o-mini-transcribe",
    "fallbacks": ["openai/whisper-1"],
    "base_url": "http://127.0.0.1:4000",
    "api_key_env": "TERMINAL_ANNOTATOR_TEST_KEY"
  }
}
""",
                encoding="utf-8",
            )

            config = transcription_config_from_env(
                {"TERMINAL_ANNOTATOR_TEST_KEY": "config-key"},
                path=path,
            )

        self.assertEqual(config.model, "openai/gpt-4o-mini-transcribe")
        self.assertEqual(config.fallbacks, ["openai/whisper-1"])
        self.assertEqual(config.base_url, "http://127.0.0.1:4000")
        self.assertEqual(config.api_key, "config-key")
        self.assertEqual(config.api_key_env, "TERMINAL_ANNOTATOR_TEST_KEY")

    def test_environment_overrides_file_config(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "config.json"
            path.write_text(
                """{
  "voice": {
    "model": "openai/whisper-1",
    "fallbacks": ["bad/model"],
    "api_key": "file-key"
  }
}
""",
                encoding="utf-8",
            )

            config = transcription_config_from_env(
                {
                    "TERMINAL_ANNOTATOR_TRANSCRIBE_MODEL": "groq/whisper-large-v3",
                    "TERMINAL_ANNOTATOR_TRANSCRIBE_FALLBACKS": "openai/whisper-1",
                    "TERMINAL_ANNOTATOR_LITELLM_API_KEY": "env-key",
                },
                path=path,
            )

        self.assertEqual(config.model, "groq/whisper-large-v3")
        self.assertEqual(config.fallbacks, ["openai/whisper-1"])
        self.assertEqual(config.api_key, "env-key")

    def test_reads_vercel_gateway_config(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "config.json"
            path.write_text(
                """{
  "voice": {
    "provider": "vercel-ai-gateway",
    "model": "openai/whisper-1",
    "base_url": "https://ai-gateway.vercel.sh/v4/ai/transcription-model",
    "api_key_env": "AI_GATEWAY_API_KEY"
  }
}
""",
                encoding="utf-8",
            )

            config = transcription_config_from_env(
                {"AI_GATEWAY_API_KEY": "vercel-key"},
                path=path,
            )

        self.assertEqual(config.provider, "vercel-ai-gateway")
        self.assertEqual(config.model, "openai/whisper-1")
        self.assertEqual(
            config.base_url,
            "https://ai-gateway.vercel.sh/v4/ai/transcription-model",
        )
        self.assertEqual(config.api_key, "vercel-key")


if __name__ == "__main__":
    unittest.main()
