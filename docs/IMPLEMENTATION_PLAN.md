# Terminal Annotator Implementation Plan

This plan implements the Linux v1 described in `spec.md`: a terminal-agnostic annotation core with a Terminator/PyGObject adapter, runtime/cache storage, and debug-only CLI commands.

## Guiding Constraints

- Keep `terminal_annotator.core` independent from GTK, VTE, Terminator, and AI-tool APIs.
- Store all annotation state outside the project directory using XDG runtime/cache paths.
- Never auto-submit inserted annotations. Insert text only, then leave final review and Enter press to the user.
- Treat the Terminator adapter as a thin integration layer around selection extraction, dialog display, and input insertion.
- Preserve annotations after insertion by changing status from `pending` to `inserted`.

## Target Package Layout

```text
terminal-annotator/
  pyproject.toml
  README.md

  terminal_annotator/
    __init__.py

    core/
      __init__.py
      annotation.py
      store.py
      session.py
      formatter.py
      cleanup.py

    cli/
      __init__.py
      main.py

    adapters/
      __init__.py

      terminator/
        __init__.py
        terminal_annotator_plugin.py
        dialog.py
        terminal_io.py

  scripts/
    install-terminator-plugin.sh
    uninstall-terminator-plugin.sh

  tests/
    core/
      test_store.py
      test_session.py
      test_formatter.py
      test_cleanup.py
    cli/
      test_main.py
```

## Phase 1: Project Bootstrap

Create the Python package, test setup, and minimal documentation.

Deliverables:

- `pyproject.toml` with package metadata, Python version, CLI entry point `terminal-ann`, and development dependencies.
- Package directories and empty `__init__.py` files.
- Initial `README.md` covering purpose, Linux/Terminator v1 scope, install caveats, and non-goals.
- Test runner configuration.

Verification:

- Package imports successfully.
- `terminal-ann --help` runs after editable install.
- Test suite runs with no tests or initial smoke tests.

## Phase 2: Core Model And Storage

Implement the terminal-agnostic annotation model and JSON session store.

Files:

- `terminal_annotator/core/annotation.py`
- `terminal_annotator/core/store.py`

Implementation tasks:

- Define `AnnotationStatus` values: `pending`, `inserted`, `cleared`.
- Define serializable annotation/session structures with timestamps.
- Resolve storage root in this order:
  1. `$XDG_RUNTIME_DIR/terminal-annotator/`
  2. `~/.cache/terminal-annotator/`
  3. `/tmp/terminal-annotator-$USER/`
- Store sessions under `sessions/<session_id>.json`.
- Implement atomic-ish JSON writes by writing a temporary file in the same directory and replacing the target.
- Create public functions:
  - `save_annotation(session_id, selected_text, comment, metadata)`
  - `get_pending_annotations(session_id)`
  - `mark_inserted(session_id, annotation_ids)`
  - `clear_session(session_id)`

Verification:

- Saving creates only runtime/cache files.
- Pending queries ignore `inserted` and `cleared` annotations.
- Marking inserted preserves annotation records.
- Clearing marks records `cleared` or creates an empty cleared state without deleting unrelated sessions.

## Phase 3: Session Identity

Implement stable session identity helpers that accept adapter-provided terminal metadata.

Files:

- `terminal_annotator/core/session.py`

Implementation tasks:

- Accept structured identity inputs such as `terminal_uuid`, `window_id`, `child_pid`, `pane_pid`, `cwd`, and optional `created_timestamp`.
- Generate short deterministic hashes for preferred identity tiers:
  1. `terminal_uuid + child_pid + cwd`
  2. `window_id + pane_pid + cwd`
  3. `child_pid + cwd + created_timestamp`
- Return session metadata separately from storage path decisions.
- Avoid using cwd as part of any path.

Verification:

- Same identity inputs produce the same session ID.
- Different panes or child PIDs produce different session IDs.
- CWD is stored as metadata only.

## Phase 4: Formatting

Implement formatter modes for pending annotations.

Files:

- `terminal_annotator/core/formatter.py`

Implementation tasks:

- Implement `format_pending_annotations(session_id, mode="ai-review")`.
- Support modes:
  - `ai-review`
  - `plain-notes`
  - `compact`
- Truncate very large selected-text previews during formatting while retaining full stored text.
- Return empty text or a clear no-op value when no pending annotations exist.

Verification:

- Output matches the spec shape for `ai-review`.
- `plain-notes` avoids AI-specific wording.
- `compact` is concise and still references selected text plus comments.
- Large selections are formatted safely without corrupting storage.

## Phase 5: CLI Debug Tool

Add the development/debug CLI.

Files:

- `terminal_annotator/cli/main.py`

Commands:

- `terminal-ann list`
- `terminal-ann format --session <id> [--mode ai-review|plain-notes|compact]`
- `terminal-ann clear --session <id>`
- `terminal-ann cleanup [--max-age-days 7]`
- Optional: `terminal-ann add --session <id> --text "..." --comment "..."`

Verification:

- CLI commands operate only on runtime/cache storage.
- Invalid sessions produce readable errors.
- CLI output is useful for manual adapter debugging.

## Phase 6: Cleanup

Implement old-session cleanup.

Files:

- `terminal_annotator/core/cleanup.py`

Implementation tasks:

- Delete or archive session files older than `max_age_days`.
- Base age on session `updated_at` where available, falling back to file mtime.
- Keep cleanup explicit via CLI or adapter-triggered maintenance, not on every operation unless lightweight.

Verification:

- Recent session files are preserved.
- Old session files are removed.
- Malformed session files do not crash cleanup.

## Phase 7: Standalone GTK Dialog Spike

Build the annotation dialog separately from the Terminator plugin first.

Files:

- `terminal_annotator/adapters/terminator/dialog.py`

Implementation tasks:

- Create a GTK dialog titled `Annotate terminal output`.
- Show selected text in a read-only preview.
- Provide a multiline comment input.
- Disable Save while comment is empty or whitespace.
- Return saved comment text to the caller.

Verification:

- Manual GTK smoke test opens and closes cleanly.
- Empty comment cannot be saved.
- Long selected text remains readable without growing beyond a practical dialog size.

## Phase 8: Terminator I/O Spike

Isolate Terminator/VTE selection and insertion behavior.

Files:

- `terminal_annotator/adapters/terminator/terminal_io.py`

Implementation tasks:

- Implement selected-text extraction using direct VTE APIs where available.
- Implement internal fallback by temporarily copying terminal selection, reading GTK clipboard, and restoring prior clipboard content where practical.
- Implement terminal input insertion using:
  1. `terminal.vte.paste_text(text)` when available
  2. `terminal.vte.feed_child(text.encode("utf-8"))` fallback
- Keep all method checks runtime-based because Terminator/VTE versions vary.

Verification:

- Manual test can read selected terminal text.
- Manual test can insert text into terminal input without pressing Enter.
- Clipboard fallback does not become a user-facing workflow.

## Phase 9: Terminator Plugin Integration

Wire the adapter into Terminator's context menu.

Files:

- `terminal_annotator/adapters/terminator/terminal_annotator_plugin.py`

Implementation tasks:

- Add context-menu items:
  - `Annotate selected text`
  - `Insert pending annotations`
  - `Clear session annotations`
- Build adapter-provided session metadata from available Terminator terminal/window/pane data.
- On annotate:
  - Read selected text.
  - Show error if empty.
  - Open dialog.
  - Save pending annotation.
- On insert:
  - Load pending annotations.
  - Format annotations.
  - Insert text into active terminal input.
  - Mark inserted only after insertion returns successfully.
- On clear:
  - Mark current session annotations cleared.

Verification:

- Right-click menu items appear in Terminator.
- Annotation flow creates a pending runtime/cache session file.
- Insert flow writes formatted text into the active pane input and does not submit it.
- Clear flow removes pending annotations from later insertions.

## Phase 10: Install And Uninstall Scripts

Add simple scripts for local Terminator plugin installation.

Files:

- `scripts/install-terminator-plugin.sh`
- `scripts/uninstall-terminator-plugin.sh`

Implementation tasks:

- Install plugin to `~/.config/terminator/plugins/terminal_annotator_plugin.py`.
- Copy the `terminal_annotator` package into the plugin directory for Terminator import resolution.
- Print restart/enable instructions.
- Uninstall copied plugin and package files only.

Verification:

- Install script creates expected files.
- Uninstall script removes only Terminal Annotator files.
- Running install twice is safe.

## Phase 11: End-To-End Manual Test Matrix

Run these in Terminator on Linux:

1. Shell session: annotate `ls` output, insert pending annotations, confirm text appears at prompt without submitting.
2. REPL session: annotate output, insert notes, confirm prompt stays editable.
3. Multi-pane session: annotate pane A, confirm pane B does not receive pane A annotations.
4. Large selection: save large selected text, confirm formatted insert is truncated but storage remains valid.
5. Clipboard fallback: if direct VTE selection API is unavailable, confirm clipboard behavior is internal and does not visibly disrupt workflow.
6. Cleanup: create old session fixture, run cleanup, confirm old file removal and recent file preservation.

## Testing Strategy

Automated tests should focus on the core and CLI because Terminator/GTK behavior is environment-dependent.

Automated:

- Storage path resolution with environment overrides.
- Save/load/status transitions.
- Session ID determinism and separation.
- Formatter output and truncation.
- Cleanup age handling.
- CLI command behavior using temporary storage roots.

Manual:

- GTK dialog behavior.
- Terminator menu registration.
- Selected text extraction across available VTE APIs.
- Terminal input insertion without auto-submit.
- Multi-pane session isolation.

## Risk Mitigations

- Terminator selected-text APIs may differ by version: centralize all VTE probing in `terminal_io.py`.
- Clipboard fallback may be fragile: keep it behind a single helper and preserve prior clipboard content best-effort.
- Session identity may collide in limited metadata cases: include a fallback creation timestamp only when stable terminal identifiers are unavailable.
- Plugin import paths may be awkward inside Terminator: install both the plugin file and package directory into Terminator's plugin directory for v1.
- GTK/PyGObject tests may not run in CI: keep core coverage high and document required manual checks.

## Recommended First Spike

Before building the full package, validate the riskiest adapter behavior:

1. Register a Terminator right-click menu item.
2. Read selected terminal text from the active pane.
3. Open the GTK annotation dialog with that text.
4. Insert sample text into active terminal input without submitting.

If this spike works, the remaining implementation is mostly core package work plus integration wiring.
