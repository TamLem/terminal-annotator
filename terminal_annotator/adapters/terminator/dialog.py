"""GTK dialog for creating annotations."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class AnnotationDialogResult:
    comment: str
    clear_pending: bool = False


def _load_gtk():
    import gi

    gi.require_version("Gdk", "3.0")
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gdk, GLib, Gtk, Pango

    return Gtk, Gdk, GLib, Pango


def ask_for_comment(
    selected_text: str,
    parent=None,
    terminal_theme: dict[str, str | bool] | None = None,
    pending_count: int = 0,
) -> AnnotationDialogResult | None:
    Gtk, Gdk, GLib, Pango = _load_gtk()

    dialog = Gtk.Dialog(
        title="Annotate terminal output",
        transient_for=parent,
        modal=True,
    )
    dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
    save_button = dialog.add_button("Save", Gtk.ResponseType.OK)
    save_button.set_sensitive(False)
    save_button.get_style_context().add_class("suggested-action")
    dialog.set_default_response(Gtk.ResponseType.OK)
    dialog.set_default_size(640, 460)
    dialog.set_resizable(True)
    dialog.get_style_context().add_class("terminal-annotator-dialog")

    content = dialog.get_content_area()
    content.set_border_width(0)

    outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    outer.set_border_width(12)
    outer.get_style_context().add_class("terminal-annotator-surface")
    content.add(outer)

    title = Gtk.Label()
    title.set_xalign(0)
    title.set_markup("<b>Add annotation</b>")
    outer.pack_start(title, False, False, 0)

    selected_frame = _section_frame(Gtk, "Selected terminal output")
    outer.pack_start(selected_frame, True, True, 0)

    preview = Gtk.TextView()
    preview.set_editable(False)
    preview.set_cursor_visible(False)
    preview.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
    preview.set_left_margin(8)
    preview.set_right_margin(8)
    preview.set_top_margin(8)
    preview.set_bottom_margin(8)
    _set_monospace(preview, Pango)
    _set_terminal_font(preview, Pango, terminal_theme)
    preview.get_style_context().add_class("terminal-annotator-preview")
    preview.get_buffer().set_text(selected_text)
    preview_scroll = Gtk.ScrolledWindow()
    preview_scroll.get_style_context().add_class("terminal-annotator-scroll")
    preview_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
    preview_scroll.set_shadow_type(Gtk.ShadowType.IN)
    preview_scroll.set_min_content_height(150)
    preview_scroll.add(preview)
    selected_frame.add(preview_scroll)

    meta_text = _selection_meta_text(selected_text)
    meta_label = Gtk.Label(label=meta_text)
    meta_label.set_xalign(0)
    meta_label.get_style_context().add_class("dim-label")
    outer.pack_start(meta_label, False, False, 0)

    comment_frame = _section_frame(Gtk, "Comment")
    outer.pack_start(comment_frame, True, True, 0)

    comment_view = Gtk.TextView()
    comment_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
    comment_view.set_left_margin(8)
    comment_view.set_right_margin(8)
    comment_view.set_top_margin(8)
    comment_view.set_bottom_margin(8)
    comment_view.set_accepts_tab(False)
    comment_view.get_style_context().add_class("terminal-annotator-editor")
    comment_scroll = Gtk.ScrolledWindow()
    comment_scroll.get_style_context().add_class("terminal-annotator-scroll")
    comment_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
    comment_scroll.set_shadow_type(Gtk.ShadowType.IN)
    comment_scroll.set_min_content_height(140)
    comment_scroll.add(comment_view)
    comment_frame.add(comment_scroll)

    hint = Gtk.Label()
    hint.set_xalign(0)
    hint.get_style_context().add_class("dim-label")
    hint.set_markup(GLib.markup_escape_text("Ctrl+Enter saves. Enter adds a new line."))
    outer.pack_start(hint, False, False, 0)

    clear_pending_check = None
    if pending_count > 0:
        clear_pending_check = Gtk.CheckButton(
            label=f"Clear {pending_count} pending annotation"
            f"{'' if pending_count == 1 else 's'} before saving"
        )
        clear_pending_check.get_style_context().add_class("terminal-annotator-check")
        outer.pack_start(clear_pending_check, False, False, 0)

    comment_buffer = comment_view.get_buffer()

    def update_save_state(*_args):
        start, end = comment_buffer.get_bounds()
        save_button.set_sensitive(bool(comment_buffer.get_text(start, end, True).strip()))

    def maybe_save(_widget, event):
        is_enter = event.keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter)
        has_control = bool(event.state & Gdk.ModifierType.CONTROL_MASK)
        if is_enter and has_control and save_button.get_sensitive():
            dialog.response(Gtk.ResponseType.OK)
            return True
        return False

    _apply_terminal_theme(Gtk, Gdk, terminal_theme)

    comment_buffer.connect("changed", update_save_state)
    comment_view.connect("key-press-event", maybe_save)
    dialog.show_all()
    comment_view.grab_focus()
    response = dialog.run()

    result = None
    if response == Gtk.ResponseType.OK:
        start, end = comment_buffer.get_bounds()
        comment = comment_buffer.get_text(start, end, True).strip()
        clear_pending = bool(clear_pending_check and clear_pending_check.get_active())
        if comment:
            result = AnnotationDialogResult(comment=comment, clear_pending=clear_pending)

    dialog.destroy()
    return result


def show_error(message: str, parent=None) -> None:
    Gtk, _Gdk, _GLib, _Pango = _load_gtk()
    dialog = Gtk.MessageDialog(
        transient_for=parent,
        modal=True,
        message_type=Gtk.MessageType.ERROR,
        buttons=Gtk.ButtonsType.OK,
        text=message,
    )
    dialog.run()
    dialog.destroy()


def _section_frame(Gtk, label: str):
    frame = Gtk.Frame(label=label)
    frame.set_shadow_type(Gtk.ShadowType.NONE)
    frame.set_hexpand(True)
    frame.set_vexpand(True)
    label_widget = frame.get_label_widget()
    if label_widget is not None:
        label_widget.set_xalign(0)
        label_widget.get_style_context().add_class("dim-label")
    return frame


def _set_monospace(text_view, Pango) -> None:
    set_monospace = getattr(text_view, "set_monospace", None)
    if callable(set_monospace):
        set_monospace(True)
    else:
        text_view.modify_font(Pango.FontDescription("Monospace 10"))


def _set_terminal_font(text_view, Pango, terminal_theme: dict[str, str | bool] | None) -> None:
    font = (terminal_theme or {}).get("font")
    if isinstance(font, str) and font.strip():
        text_view.modify_font(Pango.FontDescription(font))


def _selection_meta_text(selected_text: str) -> str:
    line_count = max(1, selected_text.count("\n") + 1)
    char_count = len(selected_text)
    line_word = "line" if line_count == 1 else "lines"
    char_word = "character" if char_count == 1 else "characters"
    return f"{line_count} {line_word}, {char_count} {char_word}"


def _apply_terminal_theme(Gtk, Gdk, terminal_theme: dict[str, str | bool] | None) -> None:
    if not terminal_theme:
        return

    foreground = str(terminal_theme.get("foreground") or "#eeeeee")
    background = str(terminal_theme.get("background") or "#1f1f1f")
    is_dark = bool(terminal_theme.get("is_dark"))

    bg_rgb = _rgb_tuple(background)
    fg_rgb = _rgb_tuple(foreground)
    surface = _hex(_blend(bg_rgb, (255, 255, 255) if is_dark else (0, 0, 0), 0.07))
    editor = _hex(_blend(bg_rgb, (255, 255, 255) if is_dark else (0, 0, 0), 0.03))
    border = _hex(_blend(bg_rgb, (255, 255, 255) if is_dark else (0, 0, 0), 0.22))
    muted = _hex(_blend(fg_rgb, bg_rgb, 0.38))

    css = f"""
    .terminal-annotator-surface {{
      background-color: {surface};
      color: {foreground};
    }}
    .terminal-annotator-surface label {{
      color: {foreground};
    }}
    .terminal-annotator-surface .dim-label {{
      color: {muted};
    }}
    textview.terminal-annotator-preview,
    textview.terminal-annotator-preview text {{
      background-color: {background};
      color: {foreground};
    }}
    textview.terminal-annotator-editor,
    textview.terminal-annotator-editor text {{
      background-color: {editor};
      color: {foreground};
    }}
    scrolledwindow.terminal-annotator-scroll {{
      border-color: {border};
    }}
    """
    provider = Gtk.CssProvider()
    provider.load_from_data(css.encode("utf-8"))
    screen = Gdk.Screen.get_default()
    if screen is not None:
        Gtk.StyleContext.add_provider_for_screen(
            screen,
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )


def _rgb_tuple(color: str) -> tuple[int, int, int]:
    color = color.strip()
    if color.startswith("#") and len(color) in {4, 7}:
        if len(color) == 4:
            return tuple(int(ch * 2, 16) for ch in color[1:4])  # type: ignore[return-value]
        return (
            int(color[1:3], 16),
            int(color[3:5], 16),
            int(color[5:7], 16),
        )
    if color.startswith("rgba("):
        values = color[5:-1].split(",")
        if len(values) >= 3:
            return tuple(int(float(value.strip())) for value in values[:3])  # type: ignore[return-value]
    return (31, 31, 31)


def _blend(first: tuple[int, int, int], second: tuple[int, int, int], amount: float) -> tuple[int, int, int]:
    return tuple(round(a * (1 - amount) + b * amount) for a, b in zip(first, second))  # type: ignore[return-value]


def _hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb)
