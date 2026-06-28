"""Audio recording helpers for the Terminator comment dialog."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from terminal_annotator.core.logging import log_event

SPEECH_CHANNELS = "1"
SPEECH_SAMPLE_RATE = "16000"


class AudioRecordingError(RuntimeError):
    """Raised when microphone recording cannot start or stop."""


class AudioRecorder:
    def __init__(self, process: subprocess.Popen, path: Path, command_name: str):
        self.process = process
        self.path = path
        self.command_name = command_name

    def stop(self, timeout: float = 5.0) -> None:
        if self.process.poll() is not None:
            log_event(
                "audio_recording_already_stopped",
                command=self.command_name,
                audio_path=str(self.path),
                returncode=self.process.returncode,
            )
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=timeout)
            log_event(
                "audio_recording_stopped",
                command=self.command_name,
                audio_path=str(self.path),
                returncode=self.process.returncode,
            )
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=timeout)
            log_event(
                "audio_recording_killed",
                command=self.command_name,
                audio_path=str(self.path),
                returncode=self.process.returncode,
            )


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
        log_event("audio_recording_start_failed", command=command[0], error=str(exc))
        raise AudioRecordingError(f"could not start {command[0]}: {exc}") from exc
    log_event("audio_recording_started", command=command[0], audio_path=str(path))
    return AudioRecorder(process=process, path=path, command_name=command[0])


def _recording_command(path: Path) -> list[str]:
    if shutil.which("parecord"):
        return [
            "parecord",
            "--file-format=wav",
            f"--channels={SPEECH_CHANNELS}",
            f"--rate={SPEECH_SAMPLE_RATE}",
            str(path),
        ]
    if shutil.which("arecord"):
        return [
            "arecord",
            "-q",
            "-f",
            "S16_LE",
            "-c",
            SPEECH_CHANNELS,
            "-r",
            SPEECH_SAMPLE_RATE,
            "-t",
            "wav",
            str(path),
        ]
    if shutil.which("ffmpeg"):
        return [
            "ffmpeg",
            "-y",
            "-f",
            "pulse",
            "-i",
            "default",
            "-ac",
            SPEECH_CHANNELS,
            "-ar",
            SPEECH_SAMPLE_RATE,
            "-sample_fmt",
            "s16",
            str(path),
        ]
    message = "No supported audio recorder found. Install parecord, arecord, or ffmpeg."
    log_event("audio_recording_no_supported_command")
    raise AudioRecordingError(message)
