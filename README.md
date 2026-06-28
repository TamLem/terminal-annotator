# Terminal Annotator

Add voice and text comments to Codex CLI, Opencode, and other terminal agents.

Terminal Annotator is a local voice-and-text commenting tool for terminal workflows. Record a quick spoken note, transcribe it into a terminal comment, and later insert the collected comments back into the active terminal input when you are ready to act on them.

It is built for review-heavy AI terminal workflows: Codex CLI, Claude Code, Aider, Opencode, shells, REPLs, database consoles, and other interactive CLIs where you need to capture corrections while staying in flow. The main workflow is voice-first, but typed comments and selected terminal context are supported too.

This project fills a small but painful gap: terminal output is easy to inspect but awkward to annotate without breaking focus. Terminal Annotator keeps comments tied to a terminal pane/session, stores them outside the project directory, and inserts a review-ready prompt only when you choose. It does not auto-submit anything.

## Status

Terminal Annotator is an early release.

- Current version: `0.2.0`
- Current platform target: Linux
- Current terminal adapter: Terminator
- Install model: local checkout only
- Published packages: none yet
- Core dependency footprint: none
- Voice transcription: LiteLLM or Vercel AI Gateway
- Optional voice dependency for LiteLLM mode: `litellm`
- Optional Terminator runtime dependency: `PyGObject`

Expect rough edges across Linux distributions, Terminator versions, desktop environments, and terminal-based AI tools. The core is intentionally terminal-agnostic so more adapters can be added without coupling the project to one terminal emulator or one AI CLI.

## What It Does

- Records voice comments and transcribes them into editable terminal notes.
- Saves typed comments when voice is not the right fit.
- Attaches selected terminal text as optional context.
- Keeps pending comments scoped to the active terminal session.
- Inserts pending comments into the active terminal input for review.
- Stores session data outside the repository.
- Provides a small `terminal-ann` CLI for debugging sessions and transcription.

The default inserted format is designed for AI terminal workflows:

```text
Apply these terminal comments:

1. Terminal comment:
Use the existing TeamMember model instead.

Address these comments before continuing.
```

You can edit the inserted text before pressing Enter. Terminal Annotator never presses Enter for you.

## Voice-First Workflow

In Terminator:

1. Press `Ctrl+Shift+A` or choose `New terminal comment`.
2. Record a voice note or type a comment.
3. Review the transcribed text before saving.
4. Press `Ctrl+Shift+Y` or choose `Insert pending comments`.
5. Edit the inserted prompt if needed, then press Enter yourself.

Selected terminal text is optional. If text is selected, it is saved as context for the comment. If nothing is selected, the comment is saved as a standalone terminal note.

## Terminator Shortcuts

In Terminator:

- `Ctrl+Shift+A`: create a new terminal comment
- `Ctrl+Shift+Y`: insert pending comments

The same actions are available from the right-click menu:

- `New terminal comment`
- `Insert pending comments`
- `Clear session comments`

## Install Locally

Clone the repository, then run the installer from the repo root:

```bash
./scripts/install-terminator-plugin.sh
```

Restart Terminator, then enable the plugin:

```text
Preferences -> Plugins -> TerminalAnnotator
```

To uninstall:

```bash
./scripts/uninstall-terminator-plugin.sh
```

There are no published PyPI, distro, Homebrew, Flatpak, Snap, or npm packages yet. For now, install from a local checkout.

## Voice Setup

The installer can configure voice transcription interactively.

Supported transcription paths:

- LiteLLM direct or proxy mode
- Vercel AI Gateway

Voice settings are written to:

```text
~/.config/terminal-annotator/config.json
```

The config file is written with `0600` permissions when created by the installer.

## Debug CLI

The CLI is mainly for development and debugging:

```bash
terminal-ann --storage-root
terminal-ann list
terminal-ann format --session demo
terminal-ann clear --session demo
terminal-ann cleanup --max-age-days 7
terminal-ann transcribe path/to/audio.wav
```

## Storage

Terminal Annotator writes session data outside the project directory.

Storage resolution order:

1. `$XDG_RUNTIME_DIR/terminal-annotator/`
2. `$XDG_CACHE_HOME/terminal-annotator/`
3. `~/.cache/terminal-annotator/`
4. `/tmp/terminal-annotator-$USER/`

This keeps comments local to the machine and avoids adding annotation files to the repository you are working on.

## Development

```bash
python3 -m unittest discover -v
bash -n scripts/install-terminator-plugin.sh scripts/uninstall-terminator-plugin.sh
python3 -m compileall terminal_annotator
```

## Adapter Contributions

More terminal adapters are welcome. If you want Terminal Annotator to support another terminal, please open a PR.

Include this information in the PR:

- Terminal emulator name
- Operating system and version
- Desktop environment or windowing system, if relevant
- Terminal version
- How selected text is read
- How text is inserted into the active terminal input
- How a stable pane/session identity is generated
- Manual test notes for creating, inserting, and clearing comments

Good adapter targets include GNOME Terminal, KDE Konsole, Alacritty, Kitty, WezTerm, iTerm2, Windows Terminal, and other terminals with enough extension or automation support to expose the required hooks.

Adapters should keep terminal-specific code under `terminal_annotator/adapters/<terminal>/` and keep the shared core independent from GUI libraries, terminal emulator APIs, and AI-tool-specific APIs.

## Design Principles

- Terminal first: comments are captured and replayed where the work is happening.
- Tool agnostic: no Codex, Claude, Aider, or shell-specific hooks are required.
- User controlled: inserted comments are reviewable text, not automatic submissions.
- Local by default: state stays on the local machine.
- Adapter friendly: terminal-specific behavior belongs in adapters, not in core.

## License

MIT
