# Terminal Annotator — Linux v1 Spec

## 1. Goal

Build a terminal-side annotation tool for AI terminal workflows and general terminal review workflows.

Primary workflow:

```text
Select text from terminal output
Right-click → Annotate selected text
Write comment in small UI
Save annotation

Later:
Right-click → Insert pending annotations
Annotations are inserted into the active terminal input
User reviews/edits
User presses Enter manually
```

This should work with tools like:

```text
Codex CLI
Claude Code
Aider
shell sessions
REPLs
database consoles
interactive CLIs
```

No dependency on a specific AI tool.
No CLI-tool hooks required.
No project-directory files.
No user-facing clipboard workflow.

---

## 2. Scope

### v1 target

```text
Platform: Linux
First terminal adapter: Terminator
UI toolkit: GTK / PyGObject
Storage: user runtime/cache directory
Language: Python
```

### v1 non-goals

```text
No Codex-specific integration
No AI-tool-specific hooks
No auto-submit
No project-local storage
No Git-tracked files
No universal terminal right-click system
No browser/editor review UI
```

---

## 3. Architecture

```text
terminal-annotator
├── core
│   ├── session identity
│   ├── annotation model
│   ├── runtime/cache storage
│   ├── formatter
│   └── cleanup
│
├── adapters
│   └── terminator
│       ├── right-click menu plugin
│       ├── selected-text extraction
│       ├── GTK annotation dialog
│       └── terminal input insertion
│
└── cli
    └── dev/debug commands only
```

The core stays terminal-agnostic and tool-agnostic.

The adapter handles terminal-specific behavior.

---

## 4. Core design

The core exposes:

```python
save_annotation(session_id, selected_text, comment, metadata)
get_pending_annotations(session_id)
format_pending_annotations(session_id)
mark_inserted(session_id, annotation_ids)
clear_session(session_id)
cleanup_old_sessions(max_age_days=7)
```

The core must not import:

```text
Gtk
Vte
terminatorlib
Codex APIs
Claude APIs
Aider APIs
tool-specific hooks
```

---

## 5. Storage location

Use runtime/cache storage outside the repo.

Resolution order:

```text
1. $XDG_RUNTIME_DIR/terminal-annotator/
2. ~/.cache/terminal-annotator/
3. /tmp/terminal-annotator-$USER/
```

Recommended:

```text
$XDG_RUNTIME_DIR/terminal-annotator/sessions/<session_id>.json
```

Fallback:

```text
~/.cache/terminal-annotator/sessions/<session_id>.json
```

No files are created in the project directory.

---

## 6. Session identity

Annotations belong to the active terminal pane/session.

Generate:

```text
session_id = hash(terminal_uuid + child_pid + cwd)
```

If `terminal_uuid` is unavailable:

```text
session_id = hash(window_id + pane_pid + cwd)
```

If only limited data is available:

```text
session_id = hash(child_pid + cwd + created_timestamp)
```

Store `cwd` only as metadata, not as a storage path.

Example session file:

```json
{
  "session_id": "8f3a91c2",
  "terminal": "terminator",
  "cwd": "/home/tamirat/project-x",
  "created_at": "2026-06-27T15:05:00+03:00",
  "updated_at": "2026-06-27T15:12:00+03:00",
  "annotations": [
    {
      "id": "001",
      "selected_text": "Create a new TeamMember relation",
      "comment": "Use the existing TeamMember model instead.",
      "status": "pending",
      "created_at": "2026-06-27T15:06:00+03:00"
    }
  ]
}
```

---

## 7. Annotation statuses

```text
pending
inserted
cleared
```

Behavior:

```text
pending   → visible for insertion
inserted  → already inserted into terminal input
cleared   → ignored
```

After insertion:

```text
pending → inserted
```

Do not delete immediately.

---

## 8. Formatter

The formatter converts pending annotations into plain terminal input text.

Default inserted block:

```text
Apply these comments from my annotations on your previous output:

1. Selected text:
"Create a new TeamMember relation"

My comment:
Use the existing TeamMember model instead.

2. Selected text:
"Add session state for board filters"

My comment:
Do not add session state. Keep this stateless using team_id and authenticated user.

Address these comments before continuing.
```

Generic version for non-AI tools:

```text
Review notes from selected terminal output:

1. Selected text:
"..."

Comment:
"..."
```

Formatter modes:

```text
ai-review
plain-notes
compact
```

Default mode:

```text
ai-review
```

---

## 9. Terminator adapter

Install location:

```text
~/.config/terminator/plugins/terminal_annotator_plugin.py
```

The plugin adds context-menu items:

```text
Annotate selected text
Insert pending annotations
Clear session annotations
```

---

## 10. Right-click action: Annotate selected text

Flow:

```text
1. User selects text in terminal output.
2. User right-clicks.
3. User chooses “Annotate selected text”.
4. Plugin reads selected text from active terminal.
5. GTK dialog opens.
6. User writes comment.
7. Plugin saves annotation to runtime/cache session file.
```

Dialog:

```text
Title: Annotate terminal output

Selected text:
[read-only preview]

Comment:
[multiline input]

Buttons:
Cancel
Save
```

Validation:

```text
- If selected text is empty: show error.
- If comment is empty: disable Save.
- If selected text is huge: save but truncate during formatting.
```

---

## 11. Right-click action: Insert pending annotations

Flow:

```text
1. User right-clicks in active terminal pane.
2. User chooses “Insert pending annotations”.
3. Plugin loads pending annotations for active session.
4. Plugin formats annotations.
5. Plugin inserts text into active terminal input.
6. User reviews/edits.
7. User presses Enter manually.
8. Plugin marks those annotations as inserted.
```

No auto-submit in v1.

---

## 12. Selected-text extraction

Preferred:

```text
Read selected text directly from terminal/VTE if available.
```

Practical internal fallback:

```text
Copy terminal selection internally,
read GTK clipboard,
restore previous clipboard.
```

This is not exposed as user workflow.

---

## 13. Terminal input insertion

Use terminal-native input insertion.

For Terminator/VTE:

```python
terminal.vte.paste_text(text)
```

Fallback:

```python
terminal.vte.feed_child(text.encode("utf-8"))
```

The adapter should check method availability at runtime.

---

## 14. CLI dev tool

Rename CLI from Codex-specific naming to generic naming:

```bash
terminal-ann list
terminal-ann format --session <id>
terminal-ann clear --session <id>
terminal-ann cleanup
```

Optional:

```bash
terminal-ann add --session <id> --text "..." --comment "..."
```

This is for development/debugging, not the main UX.

---

## 15. Repo layout

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
```

---

## 16. Installation script

```bash
#!/usr/bin/env bash
set -euo pipefail

PLUGIN_DIR="$HOME/.config/terminator/plugins"
mkdir -p "$PLUGIN_DIR"

cp terminal_annotator/adapters/terminator/terminal_annotator_plugin.py "$PLUGIN_DIR/"
cp -r terminal_annotator "$PLUGIN_DIR/terminal_annotator"

echo "Installed Terminal Annotator Terminator plugin."
echo "Restart Terminator, then enable it under Preferences → Plugins."
```

---

## 17. Development order

```text
1. Core annotation model
2. Runtime/cache store
3. Session ID generator
4. Formatter modes: ai-review, plain-notes, compact
5. CLI debug commands
6. Standalone GTK annotation dialog test
7. Terminator plugin menu items
8. Selected text extraction
9. Terminal input insertion
10. Mark inserted after successful insertion
11. Clear session annotations action
12. Installer script
13. README
```

---

## 18. Acceptance criteria

### Annotation

```text
Given selected text in Terminator,
when user clicks “Annotate selected text”,
then a dialog opens with selected text preview,
and saving creates a pending annotation in runtime/cache storage.
```

### Insert

```text
Given pending annotations for the active terminal session,
when user clicks “Insert pending annotations”,
then formatted annotation text appears in the active terminal input,
but is not submitted automatically.
```

### Tool independence

```text
The tool works regardless of whether the active terminal program is Codex CLI, Claude Code, Aider, a shell, a REPL, or another interactive CLI.
```

### Isolation

```text
No annotation files are created in the project directory.
No Git status changes occur.
```

### Session safety

```text
Annotations from one terminal pane should not appear in another unrelated pane.
```

### Data safety

```text
After insertion, annotations are marked inserted, not deleted.
```

---

## 19. Main technical risks

```text
1. Terminator plugin API may not expose selected text directly.
2. Internal clipboard use may be required for selection extraction.
3. VTE method names may vary by version.
4. Active pane/session identity may need refinement.
5. Multi-pane behavior may need testing.
```

## 20. First implementation spike

Test only this first:

```text
1. Add Terminator right-click menu item.
2. Read selected terminal text.
3. Open GTK dialog.
4. Insert text into the active terminal input.
```

Once those four work, the full implementation is straightforward.
