from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from terminal_annotator.core.formatter import format_annotations, format_pending_annotations
from terminal_annotator.core.store import save_annotation


class FormatterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.env_patch = patch.dict(os.environ, {"XDG_RUNTIME_DIR": self.tempdir.name})
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)

    def test_ai_review_format(self) -> None:
        save_annotation("session-1", "Create a new TeamMember relation", "Use existing model.")

        text = format_pending_annotations("session-1")

        self.assertIn("Apply these terminal comments", text)
        self.assertIn('"Create a new TeamMember relation"', text)
        self.assertIn("My comment:", text)
        self.assertIn("Address these comments before continuing.", text)

    def test_ai_review_format_includes_standalone_comments(self) -> None:
        save_annotation("session-1", "", "Transcribe the migration steps.")

        text = format_pending_annotations("session-1")

        self.assertIn("Terminal comment:", text)
        self.assertIn("Transcribe the migration steps.", text)
        self.assertNotIn('""', text)

    def test_plain_notes_format(self) -> None:
        text = format_annotations(
            [{"selected_text": "output", "comment": "note"}],
            mode="plain-notes",
        )

        self.assertIn("Review terminal comments:", text)
        self.assertIn("Comment:", text)
        self.assertNotIn("previous output", text)

    def test_compact_format_truncates(self) -> None:
        text = format_annotations(
            [{"selected_text": "x" * 400, "comment": "short"}],
            mode="compact",
        )

        self.assertIn("Review notes:", text)
        self.assertIn("[truncated]", text)

    def test_compact_format_handles_standalone_comments(self) -> None:
        text = format_annotations(
            [{"selected_text": "", "comment": "voice-only note"}],
            mode="compact",
        )

        self.assertEqual(text, "Review notes:\n1. voice-only note")


if __name__ == "__main__":
    unittest.main()
