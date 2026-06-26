from __future__ import annotations

import contextlib
import io
import os
import tempfile
import unittest
from unittest.mock import patch

from terminal_annotator.cli.main import main


class CliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.env_patch = patch.dict(os.environ, {"XDG_RUNTIME_DIR": self.tempdir.name})
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


if __name__ == "__main__":
    unittest.main()
