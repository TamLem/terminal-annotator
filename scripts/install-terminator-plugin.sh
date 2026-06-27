#!/usr/bin/env bash
set -euo pipefail

PLUGIN_DIR="$HOME/.config/terminator/plugins"
PACKAGE_DIR="$PLUGIN_DIR/terminal_annotator"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/terminal-annotator"
CONFIG_FILE="$CONFIG_DIR/config.json"

WITH_VOICE=0
CONFIGURE_VOICE=0
VOICE_PROVIDER=""
VOICE_MODEL="openai/whisper-1"
VOICE_FALLBACKS=""
VOICE_BASE_URL=""
VOICE_API_KEY_ENV="OPENAI_API_KEY"

if [[ $# -gt 0 ]]; then
  echo "This installer is interactive and does not accept arguments." >&2
  echo "Run: ./scripts/install-terminator-plugin.sh" >&2
  exit 2
fi

prompt_yes_no() {
  local prompt="$1"
  local default="$2"
  local value
  read -r -p "$prompt [$default]: " value || value=""
  value="${value:-$default}"
  case "$value" in
    y|Y|yes|YES|Yes)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

prompt_default() {
  local prompt="$1"
  local default="$2"
  local value
  read -r -p "$prompt [$default]: " value || value=""
  echo "${value:-$default}"
}

configure_voice_interactive() {
  echo "Configure voice annotation:"
  echo "  1) LiteLLM direct/proxy"
  echo "  2) Vercel AI Gateway"
  local choice
  read -r -p "Provider [1]: " choice || choice=""
  case "${choice:-1}" in
    2)
      VOICE_PROVIDER="vercel-ai-gateway"
      VOICE_MODEL="$(prompt_default "Transcription model" "openai/whisper-1")"
      VOICE_BASE_URL="$(prompt_default "Vercel AI Gateway transcription URL" "https://ai-gateway.vercel.sh/v4/ai/transcription-model")"
      VOICE_API_KEY_ENV="$(prompt_default "API key environment variable" "AI_GATEWAY_API_KEY")"
      VOICE_FALLBACKS=""
      ;;
    *)
      VOICE_PROVIDER="litellm"
      VOICE_MODEL="$(prompt_default "LiteLLM transcription model or proxy alias" "openai/whisper-1")"
      VOICE_FALLBACKS="$(prompt_default "Fallback models, comma-separated" "")"
      VOICE_BASE_URL="$(prompt_default "LiteLLM proxy URL, blank for direct SDK" "")"
      VOICE_API_KEY_ENV="$(prompt_default "API key environment variable" "OPENAI_API_KEY")"
      if prompt_yes_no "Install LiteLLM with pip --user" "y"; then
        WITH_VOICE=1
      fi
      ;;
  esac
}

if prompt_yes_no "Configure optional voice annotation" "y"; then
  CONFIGURE_VOICE=1
  configure_voice_interactive
fi

if [[ -z "$VOICE_PROVIDER" ]]; then
  VOICE_PROVIDER="litellm"
fi

if [[ "$VOICE_PROVIDER" == "vercel-ai-gateway" ]]; then
  if [[ -z "$VOICE_BASE_URL" ]]; then
    VOICE_BASE_URL="https://ai-gateway.vercel.sh/v4/ai/transcription-model"
  fi
  if [[ "$VOICE_API_KEY_ENV" == "OPENAI_API_KEY" ]]; then
    VOICE_API_KEY_ENV="AI_GATEWAY_API_KEY"
  fi
fi

mkdir -p "$PLUGIN_DIR"

cp terminal_annotator/adapters/terminator/terminal_annotator_plugin.py "$PLUGIN_DIR/"
rm -rf "$PACKAGE_DIR"
cp -r terminal_annotator "$PACKAGE_DIR"

if [[ "$WITH_VOICE" -eq 1 ]]; then
  python3 -m pip install --user litellm
fi

if [[ "$CONFIGURE_VOICE" -eq 1 ]]; then
  mkdir -p "$CONFIG_DIR"
  python3 - "$CONFIG_FILE" "$VOICE_PROVIDER" "$VOICE_MODEL" "$VOICE_FALLBACKS" "$VOICE_BASE_URL" "$VOICE_API_KEY_ENV" <<'PY'
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

path = Path(sys.argv[1])
provider = sys.argv[2]
model = sys.argv[3]
fallbacks = [item.strip() for item in sys.argv[4].split(",") if item.strip()]
base_url = sys.argv[5].strip() or None
api_key_env = sys.argv[6].strip() or None

data = {}
if path.exists():
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            data = loaded
    except json.JSONDecodeError:
        data = {}

voice = {
    "provider": provider,
    "model": model,
}
if fallbacks:
    voice["fallbacks"] = fallbacks
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
echo "Run this installer again if you want to change voice annotation settings."
