"""GTK dialog for creating annotations."""

from __future__ import annotations

import math
import struct
import threading
from dataclasses import dataclass, field
from pathlib import Path
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
    dialog.set_default_size(640, 460)
    dialog.set_resizable(True)
    dialog.get_style_context().add_class("terminal-annotator-dialog")

    content = dialog.get_content_area()
    content.set_border_width(0)

    outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
    outer.set_border_width(16)
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
    _set_margins(preview_scroll, 8)
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
    _set_margins(comment_scroll, 8)
    comment_scroll.add(comment_view)
    comment_frame.add(comment_scroll)

    hint = Gtk.Label()
    hint.set_xalign(0)
    hint.get_style_context().add_class("dim-label")
    hint.set_markup(
        GLib.markup_escape_text(
            "Ctrl+Enter saves. R records/stops voice outside the comment box."
        )
    )
    outer.pack_start(hint, False, False, 0)

    voice_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    spectrum_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
    action_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
    record_button = Gtk.Button()
    record_button.set_image(
        Gtk.Image.new_from_icon_name("media-record-symbolic", Gtk.IconSize.BUTTON)
    )
    record_button.set_tooltip_text("Record voice")
    spectrum_area = Gtk.DrawingArea()
    spectrum_area.set_size_request(260, 34)
    voice_status = Gtk.Label()
    voice_status.set_xalign(0.5)
    voice_status.set_hexpand(True)
    voice_status.get_style_context().add_class("dim-label")
    spectrum_row.set_center_widget(spectrum_area)
    action_row.set_center_widget(record_button)
    voice_box.pack_start(spectrum_row, False, False, 0)
    voice_box.pack_start(action_row, False, False, 0)
    voice_box.pack_start(voice_status, False, False, 0)
    outer.pack_start(voice_box, False, False, 0)

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
    spectrum_bar_count = 32
    spectrum_levels = {"value": [0.08] * spectrum_bar_count}
    spectrum_tick = {"value": 0}
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
        GLib.timeout_add(70, update_spectrum)

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

    def update_spectrum() -> bool:
        if not dialog_alive["value"]:
            return False
        audio_path = recording_state.get("path")
        if audio_path is not None:
            levels = _audio_levels(Path(audio_path), spectrum_bar_count)
        else:
            levels = _animated_levels(spectrum_tick["value"], spectrum_bar_count)
        spectrum_tick["value"] += 1
        spectrum_levels["value"] = _smooth_levels(levels, spectrum_levels["value"])
        spectrum_area.queue_draw()
        return recording_state.get("recorder") is not None

    def draw_spectrum(_area, context) -> bool:
        allocation = spectrum_area.get_allocation()
        width = max(1, allocation.width)
        height = max(1, allocation.height)
        levels = spectrum_levels["value"]
        bar_width = max(2, width / (len(levels) * 2.25))
        gap = bar_width * 1.25
        center = height / 2
        context.set_source_rgba(0.18, 0.72, 0.52, 0.18)
        context.rectangle(0, center - 0.5, width, 1)
        context.fill()
        x = (width - ((bar_width + gap) * len(levels) - gap)) / 2
        for level in levels:
            bar_height = max(3, min(height - 2, height * level))
            y = (height - bar_height) / 2
            alpha = 0.36 + min(0.56, level * 0.52)
            context.set_source_rgba(0.18, 0.72, 0.52, alpha)
            _rounded_rect(context, x, y, bar_width, bar_height, bar_width / 2)
            context.fill()
            x += bar_width + gap
        return False

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
    spectrum_area.connect("draw", draw_spectrum)
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


def _rounded_rect(context, x: float, y: float, width: float, height: float, radius: float) -> None:
    radius = max(0, min(radius, width / 2, height / 2))
    context.new_sub_path()
    context.arc(x + width - radius, y + radius, radius, -math.pi / 2, 0)
    context.arc(x + width - radius, y + height - radius, radius, 0, math.pi / 2)
    context.arc(x + radius, y + height - radius, radius, math.pi / 2, math.pi)
    context.arc(x + radius, y + radius, radius, math.pi, math.pi * 1.5)
    context.close_path()


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


def _audio_levels(path: Path, bar_count: int) -> list[float]:
    try:
        with path.open("rb") as handle:
            handle.seek(0, 2)
            size = handle.tell()
            if size <= 44:
                return [0.08] * bar_count
            read_size = min(4096, size - 44)
            handle.seek(size - read_size)
            data = handle.read(read_size)
    except OSError:
        return [0.08] * bar_count

    if len(data) < 2:
        return [0.08] * bar_count

    sample_count = len(data) // 2
    try:
        samples = struct.unpack("<" + "h" * sample_count, data[: sample_count * 2])
    except struct.error:
        return [0.08] * bar_count

    bucket_size = max(1, sample_count // bar_count)
    levels: list[float] = []
    for index in range(bar_count):
        start = index * bucket_size
        chunk = samples[start : start + bucket_size]
        if not chunk:
            levels.append(0.08)
            continue
        peak = max(abs(sample) for sample in chunk) / 32768
        mean_square = sum(sample * sample for sample in chunk) / len(chunk)
        rms = math.sqrt(mean_square) / 32768
        level = (peak * 0.35) + (rms * 0.65)
        levels.append(max(0.08, min(1.0, level * 5.5)))
    return levels


def _smooth_levels(current: list[float], previous: list[float]) -> list[float]:
    if not previous or len(previous) != len(current):
        return current

    smoothed: list[float] = []
    for new, old in zip(current, previous):
        amount = 0.78 if new > old else 0.34
        smoothed.append(old + (new - old) * amount)
    return smoothed


def _animated_levels(tick: int, bar_count: int) -> list[float]:
    return [
        0.10 + 0.08 * (1 + math.sin((tick * 0.72) + index * 0.55)) / 2
        for index in range(bar_count)
    ]


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
