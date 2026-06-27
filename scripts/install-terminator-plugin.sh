#!/usr/bin/env bash
set -euo pipefail

PLUGIN_DIR="$HOME/.config/terminator/plugins"
PACKAGE_DIR="$PLUGIN_DIR/terminal_annotator"

mkdir -p "$PLUGIN_DIR"

cp terminal_annotator/adapters/terminator/terminal_annotator_plugin.py "$PLUGIN_DIR/"
rm -rf "$PACKAGE_DIR"
cp -r terminal_annotator "$PACKAGE_DIR"

echo "Installed Terminal Annotator Terminator plugin."
echo "Restart Terminator, then enable it under Preferences > Plugins."
echo "Optional voice annotation requires litellm and provider credentials in Terminator's Python environment."
