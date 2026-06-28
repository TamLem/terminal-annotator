from __future__ import annotations

import json
import os
import tempfile
import unittest
from uuid import uuid4
from pathlib import Path
from unittest.mock import patch

from terminal_annotator.core.store import (
    clear_pending_annotations,
    clear_session,
    get_pending_annotations,
    mark_inserted,
    save_annotation,
    session_path,
    storage_root,
)


class StoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.env_patch = patch.dict(
            os.environ,
            {
                "XDG_RUNTIME_DIR": self.tempdir.name,
                "XDG_CACHE_HOME": "",
            },
        )
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)

    def test_save_annotation_writes_runtime_session_file(self) -> None:
        annotation = save_annotation(
            "session-1",
            "selected text",
            "use the existing model",
            {"terminal": "terminator", "cwd": "/tmp/project"},
        )

        path = session_path("session-1")
        self.assertTrue(path.exists())
        self.assertTrue(str(path).startswith(str(storage_root())))
        self.assertEqual(annotation["status"], "pending")

        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(data["session_id"], "session-1")
        self.assertEqual(data["terminal"], "terminator")
        self.assertEqual(data["cwd"], "/tmp/project")
        self.assertEqual(data["annotations"][0]["selected_text"], "selected text")
        self.assertEqual(
            data["annotations"][0]["metadata"]["comment_kind"],
            "terminal-comment",
        )
        self.assertTrue(data["annotations"][0]["metadata"]["has_context"])

    def test_save_comment_without_selected_text(self) -> None:
        annotation = save_annotation("session-1", "", "standalone voice note")

        self.assertEqual(annotation["selected_text"], "")
        self.assertEqual(annotation["comment"], "standalone voice note")
        self.assertEqual(annotation["metadata"]["comment_kind"], "terminal-comment")
        self.assertFalse(annotation["metadata"]["has_context"])

    def test_status_transitions_preserve_records(self) -> None:
        first = save_annotation("session-1", "one", "comment one")
        second = save_annotation("session-1", "two", "comment two")

        self.assertEqual(len(get_pending_annotations("session-1")), 2)
        self.assertEqual(mark_inserted("session-1", [first["id"]]), 1)

        pending = get_pending_annotations("session-1")
        self.assertEqual([item["id"] for item in pending], [second["id"]])

        data = json.loads(session_path("session-1").read_text(encoding="utf-8"))
        statuses = {item["id"]: item["status"] for item in data["annotations"]}
        self.assertEqual(statuses[first["id"]], "inserted")
        self.assertEqual(statuses[second["id"]], "pending")

        self.assertEqual(clear_session("session-1"), 2)
        self.assertEqual(get_pending_annotations("session-1"), [])

    def test_clear_pending_annotations_preserves_inserted_annotations(self) -> None:
        inserted = save_annotation("session-1", "one", "comment one")
        pending = save_annotation("session-1", "two", "comment two")
        self.assertEqual(mark_inserted("session-1", [inserted["id"]]), 1)

        self.assertEqual(clear_pending_annotations("session-1"), 1)

        data = json.loads(session_path("session-1").read_text(encoding="utf-8"))
        statuses = {item["id"]: item["status"] for item in data["annotations"]}
        self.assertEqual(statuses[inserted["id"]], "inserted")
        self.assertEqual(statuses[pending["id"]], "cleared")
        self.assertEqual(get_pending_annotations("session-1"), [])

    def test_session_id_is_sanitized_for_paths(self) -> None:
        path = session_path("../abc !!")
        self.assertEqual(path.name, "abc.json")
        self.assertIsInstance(path, Path)

    def test_metadata_is_json_safe(self) -> None:
        terminal_uuid = uuid4()

        save_annotation(
            "session-1",
            "selected text",
            "comment",
            {"terminal": "terminator", "terminal_uuid": terminal_uuid},
        )

        data = json.loads(session_path("session-1").read_text(encoding="utf-8"))
        self.assertEqual(data["metadata"]["terminal_uuid"], str(terminal_uuid))
        self.assertEqual(
            data["annotations"][0]["metadata"]["terminal_uuid"],
            str(terminal_uuid),
        )


if __name__ == "__main__":
    unittest.main()
