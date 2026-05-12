#!/usr/bin/env bash
set -euo pipefail
echo "[camclave] uninstalling..."
for p in "$HOME/.claude/skills/camclave" "$HOME/.codex/skills/camclave" "$HOME/.local/bin/camclave"; do
    if [[ -e "$p" || -L "$p" ]]; then
        rm -rf "$p"
        echo "  removed $p"
    fi
done
echo "[camclave] done. ~/.camclave/ kept for any captures you marked --keep."
