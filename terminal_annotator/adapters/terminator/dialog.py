"""GTK dialog for creating annotations."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from terminal_annotator.core.annotation import now_iso


@dataclass(slots=True)
class AnnotationDialogResult:
    comment: str
    clear_pending: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


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
    dialog.set_default_size(680, 560)
    dialog.set_resizable(True)
    dialog.get_style_context().add_class("terminal-annotator-dialog")

    content = dialog.get_content_area()
    content.set_border_width(0)

    outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
    outer.set_border_width(18)
    outer.get_style_context().add_class("terminal-annotator-surface")
    content.add(outer)

    header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
    header.set_hexpand(True)
    title = Gtk.Label()
    title.set_xalign(0)
    title.set_markup("<b>Add annotation</b>")
    title.get_style_context().add_class("terminal-annotator-title")
    header.pack_start(title, True, True, 0)
    outer.pack_start(header, False, False, 0)

    selected_section = _section_box(Gtk, "Selected terminal output")
    selected_body = _section_body(Gtk)
    selected_section.pack_start(selected_body, True, True, 0)
    outer.pack_start(selected_section, True, True, 0)

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
    preview_scroll.set_shadow_type(Gtk.ShadowType.NONE)
    preview_scroll.set_min_content_height(145)
    preview_scroll.add(preview)
    selected_body.pack_start(preview_scroll, True, True, 0)

    meta_text = _selection_meta_text(selected_text)
    meta_label = Gtk.Label(label=meta_text)
    meta_label.set_xalign(0)
    meta_label.get_style_context().add_class("dim-label")
    selected_section.pack_start(meta_label, False, False, 0)

    comment_section = _section_box(Gtk, "Comment")
    comment_body = _section_body(Gtk)
    comment_section.pack_start(comment_body, True, True, 0)
    outer.pack_start(comment_section, True, True, 0)

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
    comment_scroll.set_shadow_type(Gtk.ShadowType.NONE)
    comment_scroll.set_min_content_height(150)
    comment_scroll.add(comment_view)
    comment_body.pack_start(comment_scroll, True, True, 0)

    voice_panel = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
    voice_panel.get_style_context().add_class("terminal-annotator-voice")
    _set_margins(voice_panel, 2)
    voice_text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
    voice_title = Gtk.Label(label="Voice note")
    voice_title.set_xalign(0)
    voice_title.get_style_context().add_class("terminal-annotator-section-title")
    voice_hint = Gtk.Label(label="Press R to record or stop. Ctrl+Enter saves.")
    voice_hint.set_xalign(0)
    voice_hint.get_style_context().add_class("dim-label")
    voice_text.pack_start(voice_title, False, False, 0)
    voice_text.pack_start(voice_hint, False, False, 0)
    voice_spinner = Gtk.Spinner()
    voice_spinner.set_size_request(22, 22)
    record_button = Gtk.Button()
    record_button.set_image(
        Gtk.Image.new_from_icon_name("media-record-symbolic", Gtk.IconSize.BUTTON)
    )
    record_button.set_tooltip_text("Record voice")
    voice_status = Gtk.Label()
    voice_status.set_xalign(1)
    voice_status.get_style_context().add_class("dim-label")
    voice_panel.pack_start(voice_text, True, True, 0)
    voice_panel.pack_start(voice_spinner, False, False, 0)
    voice_panel.pack_start(record_button, False, False, 0)
    voice_panel.pack_start(voice_status, False, False, 0)
    outer.pack_start(voice_panel, False, False, 0)

    clear_pending_check = None
    if pending_count > 0:
        clear_pending_check = Gtk.CheckButton(
            label=f"Clear {pending_count} pending annotation"
            f"{'' if pending_count == 1 else 's'} before saving"
        )
        clear_pending_check.get_style_context().add_class("terminal-annotator-check")
        outer.pack_start(clear_pending_check, False, False, 0)

    comment_buffer = comment_view.get_buffer()
    dialog_alive = {"value": True}
    recording_state: dict[str, Any] = {"recorder": None, "path": None}
    voice_busy = {"value": False}
    result_metadata: dict[str, Any] = {}

    def update_save_state(*_args):
        start, end = comment_buffer.get_bounds()
        has_comment = bool(comment_buffer.get_text(start, end, True).strip())
        save_button.set_sensitive(has_comment and not voice_busy["value"])

    def set_voice_status(message: str) -> None:
        voice_status.set_text(message)

    def set_voice_controls(recording: bool = False, transcribing: bool = False) -> None:
        voice_busy["value"] = recording or transcribing
        record_button.set_sensitive(not transcribing)
        if recording or transcribing:
            voice_spinner.start()
        else:
            voice_spinner.stop()
        if recording:
            record_button.set_image(
                Gtk.Image.new_from_icon_name(
                    "media-playback-stop-symbolic",
                    Gtk.IconSize.BUTTON,
                )
            )
            record_button.set_tooltip_text("Stop recording")
        else:
            record_button.set_image(
                Gtk.Image.new_from_icon_name("media-record-symbolic", Gtk.IconSize.BUTTON)
            )
            record_button.set_tooltip_text("Record voice")
        update_save_state()

    def on_record_button_clicked(_button) -> None:
        if recording_state.get("recorder") is not None:
            stop_recording()
        else:
            start_recording()

    def start_recording() -> None:
        from terminal_annotator.adapters.terminator.audio_recording import (
            AudioRecordingError,
            start_audio_recording,
        )
        from terminal_annotator.core.store import audio_dir

        audio_path = audio_dir() / f"voice-{uuid4().hex}.wav"
        try:
            recorder = start_audio_recording(audio_path)
        except AudioRecordingError as exc:
            set_voice_status(str(exc))
            return
        recording_state["recorder"] = recorder
        recording_state["path"] = audio_path
        set_voice_controls(recording=True)
        set_voice_status(f"Recording with {recorder.command_name}...")

    def stop_recording() -> None:
        recorder = recording_state.get("recorder")
        audio_path = recording_state.get("path")
        recording_state["recorder"] = None
        recording_state["path"] = None
        set_voice_controls(transcribing=True)
        set_voice_status("Transcribing...")
        try:
            if recorder is not None:
                recorder.stop()
        except Exception as exc:  # noqa: BLE001 - process errors vary by recorder.
            set_voice_controls()
            set_voice_status(f"Could not stop recording: {exc}")
            return

        if audio_path is None:
            set_voice_controls()
            set_voice_status("No recording was captured.")
            return

        thread = threading.Thread(
            target=transcribe_recording,
            args=(audio_path,),
            daemon=True,
        )
        thread.start()

    def transcribe_recording(audio_path) -> None:
        try:
            from terminal_annotator.adapters.transcription import (
                transcribe_audio,
            )
            from terminal_annotator.core.transcription import (
                transcription_config_from_env,
            )

            result = transcribe_audio(audio_path, transcription_config_from_env())
        except Exception as exc:  # noqa: BLE001 - provider/network errors vary.
            GLib.idle_add(transcription_failed, str(exc))
            return
        GLib.idle_add(transcription_finished, result.text, result.to_metadata())

    def transcription_finished(text: str, metadata: dict[str, Any]) -> bool:
        if not dialog_alive["value"]:
            return False
        append_comment_text(text)
        voice_metadata = dict(metadata)
        voice_metadata["transcribed_at"] = now_iso()
        result_metadata["voice"] = voice_metadata
        set_voice_controls()
        set_voice_status("Transcript added.")
        update_save_state()
        return False

    def transcription_failed(message: str) -> bool:
        if not dialog_alive["value"]:
            return False
        set_voice_controls()
        set_voice_status(f"Transcription failed: {message}")
        return False

    def append_comment_text(text: str) -> None:
        text = text.strip()
        if not text:
            return
        start, end = comment_buffer.get_bounds()
        existing = comment_buffer.get_text(start, end, True)
        if existing.strip():
            insert_text = text if existing.endswith("\n") else f"\n{text}"
            comment_buffer.insert(end, insert_text)
        else:
            comment_buffer.set_text(text)

    def maybe_save(_widget, event):
        is_enter = event.keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter)
        keyval = Gdk.keyval_to_lower(event.keyval)
        has_control = bool(event.state & Gdk.ModifierType.CONTROL_MASK)
        if is_enter and has_control and save_button.get_sensitive():
            dialog.response(Gtk.ResponseType.OK)
            return True
        if (
            keyval == Gdk.KEY_r
            and not has_control
            and not comment_view.has_focus()
            and record_button.get_sensitive()
        ):
            on_record_button_clicked(record_button)
            return True
        return False

    _apply_terminal_theme(Gtk, Gdk, terminal_theme)

    comment_buffer.connect("changed", update_save_state)
    comment_view.connect("key-press-event", maybe_save)
    record_button.connect("clicked", on_record_button_clicked)
    dialog.show_all()
    comment_view.grab_focus()
    response = dialog.run()
    dialog_alive["value"] = False

    recorder = recording_state.get("recorder")
    if recorder is not None:
        try:
            recorder.stop()
        except Exception:
            pass

    result = None
    if response == Gtk.ResponseType.OK:
        start, end = comment_buffer.get_bounds()
        comment = comment_buffer.get_text(start, end, True).strip()
        clear_pending = bool(clear_pending_check and clear_pending_check.get_active())
        if comment:
            result = AnnotationDialogResult(
                comment=comment,
                clear_pending=clear_pending,
                metadata=result_metadata,
            )

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


def _section_box(Gtk, label: str):
    section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=7)
    section.set_hexpand(True)
    section.set_vexpand(True)
    title = Gtk.Label(label=label)
    title.set_xalign(0)
    title.get_style_context().add_class("terminal-annotator-section-title")
    section.pack_start(title, False, False, 0)
    return section


def _section_body(Gtk):
    body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
    body.set_hexpand(True)
    body.set_vexpand(True)
    body.get_style_context().add_class("terminal-annotator-section-body")
    body.set_border_width(8)
    return body


def _set_margins(widget, amount: int) -> None:
    for method_name in (
        "set_margin_top",
        "set_margin_bottom",
        "set_margin_start",
        "set_margin_end",
        "set_margin_left",
        "set_margin_right",
    ):
        method = getattr(widget, method_name, None)
        if callable(method):
            method(amount)


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
    panel = _hex(_blend(bg_rgb, (255, 255, 255) if is_dark else (0, 0, 0), 0.10))
    panel_border = _hex(_blend(bg_rgb, (255, 255, 255) if is_dark else (0, 0, 0), 0.26))

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
    .terminal-annotator-title {{
      font-size: 13px;
    }}
    .terminal-annotator-section-title {{
      color: {foreground};
      font-weight: 600;
    }}
    .terminal-annotator-section-body,
    .terminal-annotator-voice {{
      background-color: {panel};
      border: 1px solid {panel_border};
      border-radius: 6px;
    }}
    .terminal-annotator-voice {{
      padding: 10px 12px;
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
