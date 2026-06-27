"""Audio recording helpers for the Terminator annotation dialog."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class AudioRecordingError(RuntimeError):
    """Raised when microphone recording cannot start or stop."""


class AudioRecorder:
    def __init__(self, process: subprocess.Popen, path: Path, command_name: str):
        self.process = process
        self.path = path
        self.command_name = command_name

    def stop(self, timeout: float = 5.0) -> None:
        if self.process.poll() is not None:
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=timeout)


def start_audio_recording(path: Path) -> AudioRecorder:
    path.parent.mkdir(parents=True, exist_ok=True)
    command = _recording_command(path)
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as exc:
        raise AudioRecordingError(f"could not start {command[0]}: {exc}") from exc
    return AudioRecorder(process=process, path=path, command_name=command[0])


def _recording_command(path: Path) -> list[str]:
    if shutil.which("parecord"):
        return ["parecord", "--file-format=wav", str(path)]
    if shutil.which("arecord"):
        return ["arecord", "-q", "-f", "cd", "-t", "wav", str(path)]
    if shutil.which("ffmpeg"):
        return ["ffmpeg", "-y", "-f", "pulse", "-i", "default", str(path)]
    raise AudioRecordingError(
        "No supported audio recorder found. Install parecord, arecord, or ffmpeg."
    )
