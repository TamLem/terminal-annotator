from __future__ import annotations

import tempfile
import unittest
import wave
from pathlib import Path

from terminal_annotator.adapters.terminator.dialog import (
    _animated_levels,
    _audio_levels,
    _smooth_levels,
)


class DialogAudioLevelsTests(unittest.TestCase):
    def test_audio_levels_read_wav_tail(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "note.wav"
            with wave.open(str(path), "wb") as handle:
                handle.setnchannels(1)
                handle.setsampwidth(2)
                handle.setframerate(16000)
                handle.writeframes((b"\x00\x00" * 1000) + (b"\xff\x3f" * 1000))

            levels = _audio_levels(path, 8)

        self.assertEqual(len(levels), 8)
        self.assertTrue(any(level > 0.08 for level in levels))

    def test_smooth_levels_moves_toward_current_values(self) -> None:
        levels = _smooth_levels([1.0, 0.08], [0.08, 1.0])

        self.assertGreater(levels[0], 0.08)
        self.assertLess(levels[0], 1.0)
        self.assertGreater(levels[1], 0.08)
        self.assertLess(levels[1], 1.0)

    def test_animated_levels_are_bounded(self) -> None:
        levels = _animated_levels(4, 16)

        self.assertEqual(len(levels), 16)
        self.assertTrue(all(0 <= level <= 1 for level in levels))


if __name__ == "__main__":
    unittest.main()
