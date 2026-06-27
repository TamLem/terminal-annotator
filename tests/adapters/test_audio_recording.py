from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from terminal_annotator.adapters.terminator.audio_recording import (
    AudioRecordingError,
    _recording_command,
)


class AudioRecordingTests(unittest.TestCase):
    def test_prefers_parecord(self) -> None:
        def which(command: str) -> str | None:
            return f"/usr/bin/{command}" if command == "parecord" else None

        with patch("shutil.which", side_effect=which):
            command = _recording_command(Path("/tmp/note.wav"))

        self.assertEqual(command, ["parecord", "--file-format=wav", "/tmp/note.wav"])

    def test_falls_back_to_arecord(self) -> None:
        def which(command: str) -> str | None:
            return f"/usr/bin/{command}" if command == "arecord" else None

        with patch("shutil.which", side_effect=which):
            command = _recording_command(Path("/tmp/note.wav"))

        self.assertEqual(command, ["arecord", "-q", "-f", "cd", "-t", "wav", "/tmp/note.wav"])

    def test_raises_when_no_recorder_exists(self) -> None:
        with patch("shutil.which", return_value=None):
            with self.assertRaisesRegex(AudioRecordingError, "No supported audio recorder"):
                _recording_command(Path("/tmp/note.wav"))


if __name__ == "__main__":
    unittest.main()
