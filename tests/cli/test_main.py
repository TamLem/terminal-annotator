from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from terminal_annotator.cli.main import main
from terminal_annotator.core.store import session_path
from terminal_annotator.core.transcription import TranscriptionError, TranscriptionResult


class CliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.env_patch = patch.dict(
            os.environ,
            {
                "XDG_RUNTIME_DIR": self.tempdir.name,
                "XDG_CONFIG_HOME": self.tempdir.name,
            },
        )
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)

    def run_cli(self, argv: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(argv)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_add_and_format(self) -> None:
        code, stdout, stderr = self.run_cli(
            [
                "add",
                "--session",
                "demo",
                "--text",
                "selected",
                "--comment",
                "comment",
            ]
        )
        self.assertEqual(code, 0, stderr)
        self.assertTrue(stdout.strip())

        code, stdout, stderr = self.run_cli(["format", "--session", "demo"])
        self.assertEqual(code, 0, stderr)
        self.assertIn("selected", stdout)
        self.assertIn("comment", stdout)

    def test_missing_format_session_returns_error(self) -> None:
        code, stdout, stderr = self.run_cli(["format", "--session", "missing"])
        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertIn("No pending annotations", stderr)

    def test_transcribe_prints_transcript(self) -> None:
        audio_path = os.path.join(self.tempdir.name, "note.wav")
        with open(audio_path, "wb") as handle:
            handle.write(b"fake wav")

        result = TranscriptionResult(
            text="voice transcript",
            provider="litellm",
            model="openai/whisper-1",
            audio_path=audio_path,
        )

        with patch(
            "terminal_annotator.adapters.transcription.transcribe_audio",
            return_value=result,
        ):
            code, stdout, stderr = self.run_cli(["transcribe", audio_path])

        self.assertEqual(code, 0, stderr)
        self.assertEqual(stdout, "voice transcript\n")
        self.assertEqual(stderr, "")

    def test_transcribe_reports_provider_error(self) -> None:
        audio_path = os.path.join(self.tempdir.name, "note.wav")
        with open(audio_path, "wb") as handle:
            handle.write(b"fake wav")

        with patch(
            "terminal_annotator.adapters.transcription.transcribe_audio",
            side_effect=TranscriptionError("missing key"),
        ):
            code, stdout, stderr = self.run_cli(["transcribe", audio_path])

        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertIn("Transcription failed: missing key", stderr)

    def test_add_accepts_audio_path_metadata(self) -> None:
        audio_path = os.path.join(self.tempdir.name, "note.wav")
        code, stdout, stderr = self.run_cli(
            [
                "add",
                "--session",
                "demo",
                "--text",
                "selected",
                "--comment",
                "comment",
                "--audio-path",
                audio_path,
            ]
        )

        self.assertEqual(code, 0, stderr)
        self.assertTrue(stdout.strip())

        data = json.loads(session_path("demo").read_text(encoding="utf-8"))
        voice = data["annotations"][0]["metadata"]["voice"]
        self.assertEqual(voice["audio_path"], audio_path)
        self.assertEqual(voice["provider"], "debug")
        self.assertEqual(voice["model"], "manual")


if __name__ == "__main__":
    unittest.main()
