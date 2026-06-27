#!/usr/bin/env bash
set -euo pipefail

PLUGIN_DIR="$HOME/.config/terminator/plugins"
PACKAGE_DIR="$PLUGIN_DIR/terminal_annotator"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/terminal-annotator"
CONFIG_FILE="$CONFIG_DIR/config.json"

WITH_VOICE=0
CONFIGURE_VOICE=0
VOICE_MODEL="openai/whisper-1"
VOICE_FALLBACKS=""
VOICE_BASE_URL=""
VOICE_API_KEY_ENV="OPENAI_API_KEY"

usage() {
  cat <<'USAGE'
Usage: ./scripts/install-terminator-plugin.sh [options]

Options:
  --with-voice                 Install the optional LiteLLM dependency with pip.
  --configure-voice            Write ~/.config/terminal-annotator/config.json voice settings.
  --voice-model MODEL          Transcription model. Default: openai/whisper-1.
  --voice-fallbacks LIST       Comma-separated fallback models.
  --voice-base-url URL         Optional LiteLLM proxy base URL.
  --voice-api-key-env NAME     Environment variable Terminator should read for the key. Default: OPENAI_API_KEY.
  -h, --help                   Show this help.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-voice)
      WITH_VOICE=1
      ;;
    --configure-voice)
      CONFIGURE_VOICE=1
      ;;
    --voice-model)
      VOICE_MODEL="${2:?missing value for --voice-model}"
      shift
      ;;
    --voice-fallbacks)
      VOICE_FALLBACKS="${2:?missing value for --voice-fallbacks}"
      shift
      ;;
    --voice-base-url)
      VOICE_BASE_URL="${2:?missing value for --voice-base-url}"
      shift
      ;;
    --voice-api-key-env)
      VOICE_API_KEY_ENV="${2:?missing value for --voice-api-key-env}"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

mkdir -p "$PLUGIN_DIR"

cp terminal_annotator/adapters/terminator/terminal_annotator_plugin.py "$PLUGIN_DIR/"
rm -rf "$PACKAGE_DIR"
cp -r terminal_annotator "$PACKAGE_DIR"

if [[ "$WITH_VOICE" -eq 1 ]]; then
  python3 -m pip install --user litellm
fi

if [[ "$CONFIGURE_VOICE" -eq 1 ]]; then
  mkdir -p "$CONFIG_DIR"
  python3 - "$CONFIG_FILE" "$VOICE_MODEL" "$VOICE_FALLBACKS" "$VOICE_BASE_URL" "$VOICE_API_KEY_ENV" <<'PY'
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

path = Path(sys.argv[1])
model = sys.argv[2]
fallbacks = [item.strip() for item in sys.argv[3].split(",") if item.strip()]
base_url = sys.argv[4].strip() or None
api_key_env = sys.argv[5].strip() or None

data = {}
if path.exists():
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            data = loaded
    except json.JSONDecodeError:
        data = {}

voice = {
    "provider": "litellm",
    "model": model,
    "fallbacks": fallbacks,
}
if base_url:
    voice["base_url"] = base_url
if api_key_env:
    voice["api_key_env"] = api_key_env

data["voice"] = voice
path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
os.chmod(path, 0o600)
PY
fi

echo "Installed Terminal Annotator Terminator plugin."
if [[ "$CONFIGURE_VOICE" -eq 1 ]]; then
  echo "Configured voice annotation in $CONFIG_FILE."
fi
echo "Restart Terminator, then enable it under Preferences > Plugins."
echo "Voice annotation is optional. Use --with-voice --configure-voice to set it up from this script."
