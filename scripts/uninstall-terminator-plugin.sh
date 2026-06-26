#!/usr/bin/env bash
set -euo pipefail

PLUGIN_DIR="$HOME/.config/terminator/plugins"

rm -f "$PLUGIN_DIR/terminal_annotator_plugin.py"
rm -rf "$PLUGIN_DIR/terminal_annotator"

echo "Uninstalled Terminal Annotator Terminator plugin."
