from __future__ import annotations

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from terminal_annotator.core.cleanup import cleanup_old_sessions
from terminal_annotator.core.store import audio_dir, save_annotation, sessions_dir


class CleanupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.env_patch = patch.dict(os.environ, {"XDG_RUNTIME_DIR": self.tempdir.name})
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)

    def test_cleanup_removes_old_files_and_keeps_recent_files(self) -> None:
        save_annotation("recent", "text", "comment")
        directory = sessions_dir()
        old_path = directory / "old.json"
        old_path.write_text('{"session_id":"old","annotations":[]}\n', encoding="utf-8")
        old_time = time.time() - 10 * 24 * 60 * 60
        os.utime(old_path, (old_time, old_time))

        self.assertEqual(cleanup_old_sessions(max_age_days=7), 1)

        self.assertFalse(old_path.exists())
        self.assertTrue((directory / "recent.json").exists())
        self.assertIsInstance(directory, Path)

    def test_cleanup_removes_audio_referenced_by_old_session(self) -> None:
        directory = sessions_dir()
        directory.mkdir(parents=True, exist_ok=True)
        audio = audio_dir() / "old.wav"
        audio.parent.mkdir(parents=True, exist_ok=True)
        audio.write_bytes(b"audio")
        old_path = directory / "old.json"
        old_path.write_text(
            (
                '{"session_id":"old","annotations":[{"metadata":{"voice":'
                f'{{"audio_path":"{audio}"}}'
                "}}]}\n"
            ),
            encoding="utf-8",
        )
        old_time = time.time() - 10 * 24 * 60 * 60
        os.utime(old_path, (old_time, old_time))

        self.assertEqual(cleanup_old_sessions(max_age_days=7), 1)

        self.assertFalse(old_path.exists())
        self.assertFalse(audio.exists())


if __name__ == "__main__":
    unittest.main()
