from __future__ import annotations

import json
import logging
import os
import tempfile
import unittest
from unittest.mock import patch

from terminal_annotator.core.logging import LOGGER_NAME, log_event, log_path


class LoggingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.env_patch = patch.dict(os.environ, {"XDG_RUNTIME_DIR": self.tempdir.name})
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)
        logger = logging.getLogger(LOGGER_NAME)
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
            handler.close()

    def test_log_event_writes_json_and_redacts_keys(self) -> None:
        log_event(
            "voice_test",
            provider="vercel-ai-gateway",
            api_key="secret-key",
            nested={"Authorization": "Bearer secret"},
        )

        path = log_path()
        self.assertTrue(path.exists())
        line = path.read_text(encoding="utf-8").strip()
        record = json.loads(line)
        self.assertEqual(record["event"], "voice_test")
        self.assertEqual(record["provider"], "vercel-ai-gateway")
        self.assertEqual(record["api_key"], "[redacted]")
        self.assertEqual(record["nested"]["Authorization"], "[redacted]")


if __name__ == "__main__":
    unittest.main()
