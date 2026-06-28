# Release Notes

## 0.2.0 - Voice Input and Terminal Comments

Released 2026-06-28.

This release redesigns Terminal Annotator around terminal comments: selected terminal text is now optional context, and standalone typed or voice comments are saved into the same pending queue.

### Added

- Optional LiteLLM-backed voice transcription for terminal comments.
- Vercel AI Gateway transcription support.
- Interactive voice input setup in `./scripts/install-terminator-plugin.sh`.
- File-based voice settings at `~/.config/terminal-annotator/config.json`.
- Direct API-key storage with `0600` config permissions from the installer.
- `terminal-ann transcribe <audio-path>` for debugging transcription setup.
- `terminal-ann add --audio-path <path>` for voice metadata fixtures.
- `terminal-ann add --comment "..."` support for standalone comments without selected text.
- Cleanup for audio files referenced by old session files.
- Diagnostic logging for voice setup, recording, transcription requests, and failures.

### Changed

- `Ctrl+Shift+A` now opens `New terminal comment` whether or not text is selected.
- Selected terminal output is treated as optional context.
- Pending insert formatting now aggregates contextual comments and standalone comments together.
- Voice recording uses one Record/Stop button and a built-in activity spinner.
- The custom live audio visualizer is deferred to avoid adding UI latency.
- Recordings use speech-oriented mono 16 kHz WAV.
- Vercel AI Gateway uploads are compressed to MP3 first when `ffmpeg` is available.
- User-facing copy now uses terminal comments / voice input language.

### Verification

Automated checks passing for this release:

```bash
bash -n scripts/install-terminator-plugin.sh scripts/uninstall-terminator-plugin.sh
python3 -m unittest discover -v
python3 -m compileall terminal_annotator
```

Current result:

```text
Ran 41 tests
OK
```

## 0.1.0 - Initial Public Release

Terminal Annotator is now available as an early Linux/Terminator plugin for saving comments on selected terminal output and inserting those comments back into the active terminal input.

This release is focused on local AI-terminal review workflows, especially when working in OpenAI Codex CLI.

## What Works

- Annotate selected terminal output from Terminator.
- Save pending annotations for the active pane/session.
- Insert pending annotations back into the active terminal input.
- Review and edit inserted annotations before pressing Enter.
- Keep inserted annotations as stored history by marking them `inserted`.
- Clear annotations for the current session.
- Clear previous uninserted annotations from the annotation dialog before saving a new comment.
- Use split Terminator panes with pane-local pending annotations.
- Match the annotation dialog to the active terminal theme where possible.
- Use a debug CLI to list, format, add, clear, and clean up annotation sessions.

The plugin never auto-submits text. It inserts text only; the user remains responsible for final review and pressing Enter.

## Keyboard Shortcuts

- `Ctrl+Shift+A`: annotate selected terminal text.
- `Ctrl+Shift+Y`: insert pending annotations into the active terminal input.

The same actions are also available from the Terminator right-click menu:

- `Annotate selected text`
- `Insert pending annotations`
- `Clear session annotations`

## Tested Workflows

Tested:

- Terminator on Linux.
- OpenAI Codex CLI.
- Opencode, with a selection workaround.
- Split Terminator panes.
- Shell prompts.

Opencode note:

- Hold `Shift` before selecting text in Terminator so the terminal receives the mouse selection instead of Opencode capturing it.

Not yet tested:

- Claude Code.
- Aider.
- Other AI CLI apps.
- Other terminal emulators.

## Storage

Annotations are stored outside the repository in runtime/cache storage:

1. `$XDG_RUNTIME_DIR/terminal-annotator/`
2. `$XDG_CACHE_HOME/terminal-annotator/`
3. `~/.cache/terminal-annotator/`
4. `/tmp/terminal-annotator-$USER/`

No annotation state is written to the project directory.

## Install

Install the Terminator plugin locally:

```bash
./scripts/install-terminator-plugin.sh
```

Restart Terminator, then enable:

```text
Preferences -> Plugins -> TerminalAnnotator
```

Uninstall:

```bash
./scripts/uninstall-terminator-plugin.sh
```

## Verification

Automated checks passing for this release:

```bash
python3 -B -m unittest discover -v
```

Current result:

```text
Ran 14 tests
OK
```

Manual checks completed:

- Annotate and insert in OpenAI Codex CLI.
- Annotate and insert in Opencode using `Shift` before selection.
- Insert pending annotations without auto-submit.
- Confirm split panes do not share pending annotations.
- Confirm repeated insert after insertion reports no pending annotations.

## Known Limitations

- Linux and Terminator are the only supported platform/terminal target.
- GTK/PyGObject behavior can vary across distributions and Terminator versions.
- Shortcut conflicts are possible if a local Terminator config already uses `Ctrl+Shift+A` or `Ctrl+Shift+Y`.
- Clipboard fallback for selection extraction is best-effort and internal.
- Compatibility with Claude Code, Aider, and other CLI apps still needs validation.
