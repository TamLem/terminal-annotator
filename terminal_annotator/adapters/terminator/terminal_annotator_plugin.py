"""Terminator context-menu plugin."""

from __future__ import annotations

try:
    import gi

    gi.require_version("Gdk", "3.0")
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gdk, GLib, Gtk
    from terminatorlib import plugin
    from terminatorlib.terminator import Terminator
except (ImportError, ValueError):
    Gdk = None
    GLib = None
    Gtk = None
    Terminator = None
    plugin = None

from terminal_annotator.adapters.terminator.dialog import ask_for_comment, show_error
from terminal_annotator.adapters.terminator.terminal_io import (
    get_selected_text,
    insert_text,
    terminal_theme,
    terminal_identity,
)
from terminal_annotator.core.formatter import format_annotations
from terminal_annotator.core.session import generate_session_id, session_metadata
from terminal_annotator.core.store import (
    clear_pending_annotations,
    clear_session,
    get_pending_annotations,
    mark_inserted,
    save_annotation,
)

AVAILABLE = ["TerminalAnnotator"]
ANNOTATE_SHORTCUT_LABEL = "Ctrl+Shift+A"
INSERT_SHORTCUT_LABEL = "Ctrl+Shift+Y"


if plugin is not None:

    class TerminalAnnotator(plugin.MenuItem):
        capabilities = ["terminal_menu"]

        def __init__(self):
            super().__init__()
            self._shortcut_handlers = {}
            self._terminator = None
            self._shortcut_scan_id = None

            try:
                self._terminator = Terminator()
            except Exception:
                self._terminator = None

            if self._terminator is not None:
                self._shortcut_scan_id = GLib.timeout_add(1000, self._bind_known_terminals)
                GLib.idle_add(self._bind_known_terminals_once)

        def unload(self):
            if self._shortcut_scan_id is not None and GLib is not None:
                GLib.source_remove(self._shortcut_scan_id)
                self._shortcut_scan_id = None

            for target, handler_id in list(self._shortcut_handlers.values()):
                try:
                    target.disconnect(handler_id)
                except (TypeError, RuntimeError):
                    pass
                if getattr(target, "_terminal_annotator_shortcuts", False):
                    setattr(target, "_terminal_annotator_shortcuts", False)
            self._shortcut_handlers.clear()

        def callback(self, menuitems, menu, terminal):
            self._ensure_shortcuts(terminal)

            annotate_item = Gtk.MenuItem(
                label=f"Annotate selected text    {ANNOTATE_SHORTCUT_LABEL}"
            )
            annotate_item.connect("activate", self._annotate_selected_text, terminal)
            menuitems.append(annotate_item)

            insert_item = Gtk.MenuItem(
                label=f"Insert pending annotations    {INSERT_SHORTCUT_LABEL}"
            )
            insert_item.connect("activate", self._insert_pending_annotations, terminal)
            menuitems.append(insert_item)

            clear_item = Gtk.MenuItem(label="Clear session annotations")
            clear_item.connect("activate", self._clear_session_annotations, terminal)
            menuitems.append(clear_item)

        def _session(self, terminal):
            identity = terminal_identity(terminal)
            return generate_session_id(identity), session_metadata(identity)

        def _bind_known_terminals_once(self):
            self._bind_known_terminals()
            return False

        def _bind_known_terminals(self):
            if self._terminator is None:
                return False
            for terminal in list(getattr(self._terminator, "terminals", []) or []):
                self._ensure_shortcuts(terminal)
            return True

        def _ensure_shortcuts(self, terminal):
            target = _shortcut_target_for_terminal(terminal)
            if target is None:
                return

            target_id = id(target)
            if target_id in self._shortcut_handlers:
                return

            if getattr(target, "_terminal_annotator_shortcuts", False):
                return

            handler_id = target.connect("key-press-event", self._handle_keypress, terminal)
            self._shortcut_handlers[target_id] = (target, handler_id)
            setattr(target, "_terminal_annotator_shortcuts", True)

        def _handle_keypress(self, _widget, event, terminal):
            if Gdk is None:
                return False

            keyval = Gdk.keyval_to_lower(event.keyval)
            if keyval == Gdk.KEY_a and _has_exact_modifiers(
                event,
                Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK,
            ):
                self._annotate_selected_text(None, terminal)
                return True
            if keyval == Gdk.KEY_y and _has_exact_modifiers(
                event,
                Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK,
            ):
                self._insert_pending_annotations(None, terminal)
                return True
            return False

        def _annotate_selected_text(self, _menuitem, terminal):
            parent = _window_for_terminal(terminal)
            try:
                selected_text = get_selected_text(terminal).strip()
                if not selected_text:
                    show_error("No terminal text is selected.", parent=parent)
                    return

                session_id, metadata = self._session(terminal)
                pending_count = len(get_pending_annotations(session_id))
                result = ask_for_comment(
                    selected_text,
                    parent=parent,
                    terminal_theme=terminal_theme(terminal),
                    pending_count=pending_count,
                )
                if not result:
                    return

                if result.clear_pending:
                    clear_pending_annotations(session_id)
                save_annotation(session_id, selected_text, result.comment, metadata)
            except Exception as exc:
                show_error(f"Could not save annotation: {exc}", parent=parent)

        def _insert_pending_annotations(self, _menuitem, terminal):
            parent = _window_for_terminal(terminal)
            try:
                session_id, _metadata = self._session(terminal)
                annotations = get_pending_annotations(session_id)
                if not annotations:
                    show_error("No pending annotations for this terminal session.", parent=parent)
                    return

                text = format_annotations(annotations, mode="ai-review")
                insert_text(terminal, text)
                mark_inserted(session_id, [item["id"] for item in annotations])
            except Exception as exc:
                show_error(f"Could not insert annotations: {exc}", parent=parent)

        def _clear_session_annotations(self, _menuitem, terminal):
            parent = _window_for_terminal(terminal)
            try:
                session_id, _metadata = self._session(terminal)
                clear_session(session_id)
            except Exception as exc:
                show_error(f"Could not clear annotations: {exc}", parent=parent)

else:

    class TerminalAnnotator:
        capabilities: list[str] = []


def _window_for_terminal(terminal):
    get_toplevel = getattr(terminal, "get_toplevel", None)
    if callable(get_toplevel):
        window = get_toplevel()
        if Gtk is not None and isinstance(window, Gtk.Window):
            return window

    vte = getattr(terminal, "vte", None)
    get_toplevel = getattr(vte, "get_toplevel", None)
    if callable(get_toplevel):
        window = get_toplevel()
        if Gtk is not None and isinstance(window, Gtk.Window):
            return window

    return None


def _shortcut_target_for_terminal(terminal):
    vte = getattr(terminal, "vte", None)
    if vte is not None and hasattr(vte, "connect"):
        return vte
    if hasattr(terminal, "connect"):
        return terminal
    return None


def _has_exact_modifiers(event, required):
    modifier_mask = (
        Gdk.ModifierType.CONTROL_MASK
        | Gdk.ModifierType.SHIFT_MASK
        | Gdk.ModifierType.MOD1_MASK
        | Gdk.ModifierType.SUPER_MASK
        | Gdk.ModifierType.HYPER_MASK
    )
    return event.state & modifier_mask == required
