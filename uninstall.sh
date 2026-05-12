#!/usr/bin/env bash
set -euo pipefail
echo "[lookhere] uninstalling..."
for p in "$HOME/.claude/skills/lookhere" "$HOME/.codex/skills/lookhere" "$HOME/.local/bin/lookhere"; do
    if [[ -e "$p" || -L "$p" ]]; then
        rm -rf "$p"
        echo "  removed $p"
    fi
done
echo "[lookhere] done. ~/.lookhere/ kept for any captures you marked --keep."
