"""Terminator/VTE runtime helpers."""

from __future__ import annotations

import os
from typing import Any


def vte_for_terminal(terminal: Any) -> Any:
    return getattr(terminal, "vte", terminal)


def get_selected_text(terminal: Any) -> str:
    vte = vte_for_terminal(terminal)

    for method_name in ("get_selected_text", "get_selection"):
        method = getattr(vte, method_name, None)
        if callable(method):
            value = method()
            if value:
                return str(value)

    text = _copy_selection_via_clipboard(vte)
    return text or ""


def insert_text(terminal: Any, text: str) -> None:
    vte = vte_for_terminal(terminal)
    paste_text = getattr(vte, "paste_text", None)
    if callable(paste_text):
        paste_text(text)
        return

    feed_child = getattr(vte, "feed_child", None)
    if callable(feed_child):
        data = text.encode("utf-8")
        try:
            feed_child(data)
        except TypeError:
            feed_child(data, len(data))
        return

    raise RuntimeError("terminal input insertion is not available")


def terminal_identity(terminal: Any) -> dict[str, Any]:
    vte = vte_for_terminal(terminal)
    identity: dict[str, Any] = {"terminal": "terminator"}

    cwd = _call_first(terminal, ("get_cwd", "get_current_directory"))
    if not cwd:
        cwd = _call_first(vte, ("get_current_directory_uri",))
        if isinstance(cwd, str) and cwd.startswith("file://"):
            cwd = cwd[7:]
    identity["cwd"] = cwd or os.getcwd()

    terminal_uuid = getattr(terminal, "uuid", None) or getattr(terminal, "terminator_uuid", None)
    if terminal_uuid:
        identity["terminal_uuid"] = terminal_uuid

    window = getattr(terminal, "window", None) or getattr(terminal, "parent", None)
    window_id = getattr(window, "uuid", None) or getattr(window, "title", None)
    if window_id:
        identity["window_id"] = window_id

    child_pid = _call_first(vte, ("get_pid", "get_child_pid"))
    if not child_pid:
        child_pid = getattr(terminal, "pid", None)
    if child_pid:
        identity["child_pid"] = child_pid
        identity["pane_pid"] = child_pid

    return identity


def terminal_theme(terminal: Any) -> dict[str, str | bool]:
    foreground = _rgba_from_value(getattr(terminal, "fgcolor_active", None))
    background = _rgba_from_value(getattr(terminal, "bgcolor", None))

    config = getattr(terminal, "config", None)
    if foreground is None and config is not None:
        foreground = _rgba_from_value(_config_value(config, "foreground_color"))
    if background is None and config is not None:
        background = _rgba_from_value(_config_value(config, "background_color"))

    if foreground is None:
        foreground = "#eeeeee" if _is_dark_color(background or "#000000") else "#222222"
    if background is None:
        background = "#1f1f1f" if _is_dark_color(foreground) else "#ffffff"

    theme: dict[str, str | bool] = {
        "foreground": foreground,
        "background": background,
        "is_dark": _is_dark_color(background),
    }

    vte = vte_for_terminal(terminal)
    get_font = getattr(vte, "get_font", None)
    if callable(get_font):
        try:
            font = get_font()
            to_string = getattr(font, "to_string", None)
            if callable(to_string):
                theme["font"] = to_string()
        except (TypeError, RuntimeError):
            pass

    return theme


def _call_first(obj: Any, method_names: tuple[str, ...]) -> Any:
    for method_name in method_names:
        method = getattr(obj, method_name, None)
        if callable(method):
            try:
                return method()
            except TypeError:
                continue
    return None


def _copy_selection_via_clipboard(vte: Any) -> str:
    copy_clipboard = getattr(vte, "copy_clipboard", None)
    if not callable(copy_clipboard):
        return ""

    try:
        import gi

        gi.require_version("Gtk", "3.0")
        from gi.repository import Gdk, Gtk
    except (ImportError, ValueError):
        return ""

    clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
    previous_text = clipboard.wait_for_text()
    copy_clipboard()
    while Gtk.events_pending():
        Gtk.main_iteration_do(False)
    selected_text = clipboard.wait_for_text() or ""

    if previous_text is not None:
        clipboard.set_text(previous_text, -1)
        clipboard.store()
    return selected_text


def _config_value(config: Any, key: str) -> Any:
    try:
        return config[key]
    except (KeyError, TypeError):
        return None


def _rgba_from_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value if value.startswith("#") else None

    red = getattr(value, "red", None)
    green = getattr(value, "green", None)
    blue = getattr(value, "blue", None)
    if red is None or green is None or blue is None:
        return None

    alpha = getattr(value, "alpha", 1.0)
    if alpha is None or alpha >= 0.999:
        return "#{:02x}{:02x}{:02x}".format(
            _channel_to_int(red),
            _channel_to_int(green),
            _channel_to_int(blue),
        )
    return "rgba({}, {}, {}, {:.3f})".format(
        _channel_to_int(red),
        _channel_to_int(green),
        _channel_to_int(blue),
        max(0.0, min(float(alpha), 1.0)),
    )


def _channel_to_int(value: Any) -> int:
    return max(0, min(round(float(value) * 255), 255))


def _is_dark_color(color: str) -> bool:
    red, green, blue = _rgb_tuple(color)
    luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue
    return luminance < 140


def _rgb_tuple(color: str) -> tuple[int, int, int]:
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

    return (0, 0, 0)
