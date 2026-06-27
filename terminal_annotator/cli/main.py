"""Development/debug command line interface."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from terminal_annotator.core.cleanup import cleanup_old_sessions
from terminal_annotator.core.formatter import VALID_MODES, format_pending_annotations
from terminal_annotator.core.store import (
    clear_session,
    list_sessions,
    save_annotation,
    storage_root,
)
from terminal_annotator.core.transcription import (
    TranscriptionError,
    transcription_config_from_env,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="terminal-ann")
    parser.add_argument(
        "--storage-root",
        action="store_true",
        help="print the resolved storage root and exit",
    )
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("list", help="list known sessions")

    format_parser = subparsers.add_parser("format", help="format pending annotations")
    format_parser.add_argument("--session", required=True)
    format_parser.add_argument(
        "--mode",
        choices=sorted(VALID_MODES),
        default="ai-review",
    )

    clear_parser = subparsers.add_parser("clear", help="clear annotations for a session")
    clear_parser.add_argument("--session", required=True)

    cleanup_parser = subparsers.add_parser("cleanup", help="remove old session files")
    cleanup_parser.add_argument("--max-age-days", type=int, default=7)

    transcribe_parser = subparsers.add_parser(
        "transcribe",
        help="transcribe an audio file for debugging",
    )
    transcribe_parser.add_argument("audio_path")
    transcribe_parser.add_argument("--model")

    add_parser = subparsers.add_parser("add", help="add an annotation for debugging")
    add_parser.add_argument("--session", required=True)
    add_parser.add_argument("--text", required=True)
    add_parser.add_argument("--comment", required=True)
    add_parser.add_argument("--terminal", default="cli")
    add_parser.add_argument("--cwd")
    add_parser.add_argument("--audio-path")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.storage_root:
        print(storage_root())
        return 0

    if args.command == "list":
        sessions = list_sessions()
        if not sessions:
            print("No sessions.")
            return 0
        print(json.dumps(sessions, indent=2))
        return 0

    if args.command == "format":
        text = format_pending_annotations(args.session, mode=args.mode)
        if not text:
            print(f"No pending annotations for session {args.session}.", file=sys.stderr)
            return 1
        print(text, end="")
        return 0

    if args.command == "clear":
        changed = clear_session(args.session)
        print(f"Cleared {changed} annotations.")
        return 0

    if args.command == "cleanup":
        removed = cleanup_old_sessions(max_age_days=args.max_age_days)
        print(f"Removed {removed} old session files.")
        return 0

    if args.command == "transcribe":
        from terminal_annotator.adapters.transcription import (
            transcribe_audio,
        )

        config = transcription_config_from_env()
        if args.model:
            config.model = args.model
        try:
            result = transcribe_audio(Path(args.audio_path), config)
        except TranscriptionError as exc:
            print(f"Transcription failed: {exc}", file=sys.stderr)
            return 1
        print(result.text)
        return 0

    if args.command == "add":
        metadata = {"terminal": args.terminal}
        if args.cwd:
            metadata["cwd"] = args.cwd
        if args.audio_path:
            metadata["voice"] = {
                "audio_path": str(Path(args.audio_path)),
                "provider": "debug",
                "model": "manual",
            }
        annotation = save_annotation(
            args.session,
            args.text,
            args.comment,
            metadata=metadata,
        )
        print(annotation["id"])
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
