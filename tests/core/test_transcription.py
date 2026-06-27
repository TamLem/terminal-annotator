from __future__ import annotations

import unittest

from terminal_annotator.core.transcription import transcription_config_from_env


class TranscriptionConfigTests(unittest.TestCase):
    def test_defaults_to_litellm_whisper(self) -> None:
        config = transcription_config_from_env({})

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
            }
        )

        self.assertEqual(config.provider, "litellm")
        self.assertEqual(config.model, "groq/whisper-large-v3")
        self.assertEqual(
            config.model_chain,
            ["groq/whisper-large-v3", "openai/whisper-1", "deepgram/nova-2"],
        )
        self.assertEqual(config.base_url, "http://127.0.0.1:4000")
        self.assertEqual(config.api_key, "proxy-key")


if __name__ == "__main__":
    unittest.main()
