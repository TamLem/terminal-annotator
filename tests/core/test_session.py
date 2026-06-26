from __future__ import annotations

import unittest

from terminal_annotator.core.session import generate_session_id, session_metadata


class SessionTests(unittest.TestCase):
    def test_session_id_is_deterministic(self) -> None:
        identity = {
            "terminal": "terminator",
            "terminal_uuid": "term-a",
            "child_pid": 123,
            "cwd": "/tmp/project",
        }
        self.assertEqual(generate_session_id(identity), generate_session_id(identity))

    def test_session_id_separates_panes(self) -> None:
        base = {
            "terminal_uuid": "term-a",
            "child_pid": 123,
            "cwd": "/tmp/project",
        }
        other = dict(base, child_pid=456)
        self.assertNotEqual(generate_session_id(base), generate_session_id(other))

    def test_metadata_keeps_cwd_as_metadata(self) -> None:
        metadata = session_metadata(
            {
                "terminal": "terminator",
                "cwd": "/home/user/project",
                "child_pid": 123,
                "ignored": "value",
            }
        )
        self.assertEqual(metadata["cwd"], "/home/user/project")
        self.assertNotIn("ignored", metadata)


if __name__ == "__main__":
    unittest.main()
