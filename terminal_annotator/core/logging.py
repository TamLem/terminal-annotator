"""Small append-only file logger for local diagnostics."""

from __future__ import annotations

import json
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from terminal_annotator.core.annotation import json_safe_dict, now_iso

LOGGER_NAME = "terminal_annotator"
LOG_FILENAME = "terminal-annotator.log"
APP_DIRNAME = "terminal-annotator"
SENSITIVE_KEYS = {"api_key", "authorization", "token", "secret", "password"}


def _storage_root() -> Path:
    xdg_runtime = os.environ.get("XDG_RUNTIME_DIR")
    if xdg_runtime:
        return Path(xdg_runtime) / APP_DIRNAME

    cache_home = os.environ.get("XDG_CACHE_HOME")
    if cache_home:
        return Path(cache_home) / APP_DIRNAME

    home = Path.home()
    if str(home) != "/":
        return home / ".cache" / APP_DIRNAME

    user = os.environ.get("USER") or "unknown"
    return Path("/tmp") / f"{APP_DIRNAME}-{user}"


def logs_dir() -> Path:
    return _storage_root() / "logs"


def log_path():
    return logs_dir() / LOG_FILENAME


def get_logger() -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    if logger.handlers:
        return logger

    directory = logs_dir()
    directory.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        log_path(),
        maxBytes=256 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


def log_event(event: str, **fields: Any) -> None:
    record = {
        "timestamp": now_iso(),
        "event": event,
        **json_safe_dict(_redact(fields)),
    }
    try:
        get_logger().info(json.dumps(record, sort_keys=True, ensure_ascii=False))
    except Exception:
        return


def _redact(value: Any, key: str | None = None) -> Any:
    if key and _is_sensitive_key(key):
        return "[redacted]"
    if isinstance(value, dict):
        return {str(item_key): _redact(item_value, str(item_key)) for item_key, item_value in value.items()}
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, tuple):
        return [_redact(item) for item in value]
    return value


def _is_sensitive_key(key: str) -> bool:
    lower = key.lower()
    return lower in SENSITIVE_KEYS or lower.endswith("_key") or "api_key" in lower
