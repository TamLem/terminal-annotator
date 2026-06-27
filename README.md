# Terminal Annotator

Terminal Annotator is a Linux terminal-side annotation tool for reviewing terminal output and inserting saved comments back into the active terminal input.

It is designed for AI terminal workflows, but it does not depend on any specific AI CLI. You select terminal output, save comments in a small GTK dialog, then insert those pending comments into the prompt when you are ready to continue.

The first adapter targets Terminator on Linux. The core package is terminal-agnostic and stores annotation data outside the project directory in XDG runtime/cache storage.

See [RELEASE_NOTES.md](RELEASE_NOTES.md) for the initial public release summary.

## Usage

Annotate output:

1. Select text in a Terminator pane.
2. Right-click and choose `Annotate selected text`, or press `Ctrl+Shift+A`.
3. Add your comment.
4. Save.

Insert pending annotations:

1. Focus the pane where you want the comments inserted.
2. Right-click and choose `Insert pending annotations`, or press `Ctrl+Shift+Y`.
3. Review or edit the inserted text.
4. Press Enter yourself when ready.

The plugin never auto-submits text.

Clear current session annotations:

- Right-click and choose `Clear session annotations`.
- This clears annotations for the active pane/session.

Clear previous uninserted annotations while adding a new one:

- If the current session already has pending annotations, the annotation dialog shows a checkbox to clear those pending annotations before saving the new comment.
- Inserted annotations are left intact.

## Opencode Selection Note

Opencode can capture mouse input before the terminal selection happens. In Terminator, hold `Shift` before selecting text to force normal terminal selection, then annotate as usual.

This is an Opencode interaction detail, not a Terminal Annotator integration.


## Status

This is early local tooling, but the core workflow is usable.

Tested:

- Terminator on Linux.
- OpenAI Codex CLI.
- Opencode, with a selection workaround: hold `Shift` before selecting text so the terminal receives the mouse selection instead of Opencode capturing it.
- Split Terminator panes, including pane-local pending annotations.

Not yet tested:

- Voice annotation end-to-end in Terminator.
- Claude Code.
- Aider.
- Other interactive CLI apps.
- Other terminal emulators.

The tool should work best with CLI apps that allow normal terminal text selection and accept pasted/input text at the prompt. There are no Codex-, Opencode-, Claude-, or Aider-specific hooks.

## Features

- Annotate selected terminal output from a Terminator right-click menu.
- Save annotations per active terminal pane/session.
- Insert pending annotations into terminal input without submitting them.
- Preserve inserted annotations as history by marking them `inserted`.
- Clear pending annotations for the current session.
- Optional checkbox in the annotation dialog to clear previous uninserted annotations before saving a new one.
- Keyboard shortcuts:
  - `Ctrl+Shift+A`: annotate selected text.
  - `Ctrl+Shift+Y`: insert pending annotations.
- Optional voice annotation:
  - Record from the annotation dialog.
  - Transcribe through LiteLLM.
  - Insert the transcript into the existing comment box before saving.
- Theme-aware annotation dialog that follows the active terminal profile where possible.
- Debug CLI for listing, formatting, adding, clearing, and cleaning up stored annotations.

## Install

Requirements:

- Linux.
- Terminator.
- Python 3.10+.
- GTK/PyGObject available to Terminator.
- Optional for voice: LiteLLM provider credentials and one recorder command: `parecord`, `arecord`, or `ffmpeg`.

Install the Terminator plugin locally:

```bash
./scripts/install-terminator-plugin.sh
```

Install with voice support:

```bash
./scripts/install-terminator-plugin.sh
```

The installer is interactive. It asks whether to configure optional voice annotation, then guides you through LiteLLM or Vercel AI Gateway setup.

Then fully restart Terminator and enable the plugin under:

```text
Preferences -> Plugins -> TerminalAnnotator
```

The install script copies the plugin and package into:

```text
~/.config/terminator/plugins/
```

Run the install script again after making local code changes.

Uninstall:

```bash
./scripts/uninstall-terminator-plugin.sh
```

## Voice Annotation

Voice annotation is optional. It records audio from the annotation dialog, transcribes it through LiteLLM, then inserts the transcript into the normal comment editor so you can review and edit before saving.

The recommended setup is through the interactive install script:

```bash
./scripts/install-terminator-plugin.sh
```

It copies the plugin files, asks whether to configure voice annotation, and writes:

```text
~/.config/terminal-annotator/config.json
```

Example config:

```json
{
  "voice": {
    "provider": "litellm",
    "model": "openai/whisper-1",
    "fallbacks": ["groq/whisper-large-v3", "openai/whisper-1"],
    "api_key_env": "OPENAI_API_KEY"
  }
}
```

Keep provider secrets in the referenced environment variable, for example `OPENAI_API_KEY`, or use LiteLLM's normal provider-specific environment variables. Environment variables like `TERMINAL_ANNOTATOR_TRANSCRIBE_MODEL` still work as temporary overrides.
The installer stores the entered API key directly in `config.json` and sets file permissions to `0600`. Advanced users can manually use `api_key_env` instead.

Example Vercel config:

```json
{
  "voice": {
    "provider": "vercel-ai-gateway",
    "model": "openai/whisper-1",
    "base_url": "https://ai-gateway.vercel.sh/v4/ai/transcription-model",
    "api_key": "..."
  }
}
```

Optional LiteLLM proxy setup:

Choose LiteLLM in the installer, enter your proxy alias as the model, and enter the proxy URL when prompted.

The dialog uses the first available recorder command in this order:

1. `parecord`
2. `arecord`
3. `ffmpeg`

Recorded audio is stored under the existing runtime/cache storage root in `audio/`. It is attached as annotation metadata; inserted annotations still use the transcribed text from `comment`.

## Development CLI

The CLI is primarily for debugging storage and formatting.

```bash
python3 -m terminal_annotator.cli.main --help
python3 -m terminal_annotator.cli.main --storage-root
python3 -m terminal_annotator.cli.main list
python3 -m terminal_annotator.cli.main add --session demo --text "selected output" --comment "my note"
python3 -m terminal_annotator.cli.main add --session demo --text "selected output" --comment "voice note" --audio-path ./note.wav
python3 -m terminal_annotator.cli.main transcribe ./note.wav
python3 -m terminal_annotator.cli.main format --session demo
python3 -m terminal_annotator.cli.main clear --session demo
python3 -m terminal_annotator.cli.main cleanup
```

If installed as a package, the `terminal-ann` entry point exposes the same commands:

```bash
terminal-ann list
terminal-ann transcribe ./note.wav
terminal-ann format --session demo
terminal-ann clear --session demo
terminal-ann cleanup
```

Voice transcription is optional. LiteLLM mode requires LiteLLM plus provider credentials supported by LiteLLM. Vercel AI Gateway mode requires an AI Gateway key. The install script can write the voice config file and can install LiteLLM when needed. When using LiteLLM mode in the Terminator plugin, LiteLLM must be importable from the Python environment Terminator uses.

## Storage

Session files are stored outside the repository using this order:

1. `$XDG_RUNTIME_DIR/terminal-annotator/`
2. `$XDG_CACHE_HOME/terminal-annotator/`
3. `~/.cache/terminal-annotator/`
4. `/tmp/terminal-annotator-$USER/`

Session files live under:

```text
sessions/<session_id>.json
```

Annotation statuses:

- `pending`: available for insertion.
- `inserted`: already inserted into terminal input.
- `cleared`: ignored by future insertions.

No annotation files are written to the project directory.

## Architecture

```text
terminal_annotator/
  core/
    annotation model
    session identity
    runtime/cache storage
    formatter
    cleanup
    transcription config
  adapters/
    terminator/
      right-click menu plugin
      selected-text extraction
      GTK annotation dialog
      terminal input insertion
      optional voice recording
    transcription/
      LiteLLM provider
  cli/
    debug commands
```

The core package does not import GTK, VTE, Terminator, or AI-tool APIs. Terminal-specific behavior is isolated in the adapter.

## Local Verification

Run automated checks:

```bash
python3 -m unittest discover -v
python3 -m compileall terminal_annotator
python3 -m terminal_annotator.cli.main --help
```

Suggested manual checks in Terminator:

1. Annotate normal shell output and insert pending annotations.
2. Confirm inserted text appears at the prompt without being submitted.
3. Repeat in split panes and confirm pending annotations stay pane-local.
4. Test inside OpenAI Codex CLI.
5. Test inside Opencode using `Shift` before text selection.
6. Optional voice: record a short note, confirm the transcript appears in the comment box before saving, then insert it.

## Limitations

- Linux and Terminator are the only supported target for now.
- GTK/PyGObject behavior can vary by distribution and Terminator version.
- Clipboard fallback for selected-text extraction is best-effort and only used internally when direct selection APIs are unavailable.
- Shortcut conflicts can still happen if a local Terminator configuration already uses `Ctrl+Shift+A` or `Ctrl+Shift+Y`.
- Voice transcription requires local recorder tooling and cloud/API credentials.
- Compatibility with Claude Code, Aider, and other CLI apps has not been verified yet.

## License

MIT.
