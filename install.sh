#!/usr/bin/env bash
# camclave install.sh — macOS / Linux installer
set -euo pipefail

repo="$(cd "$(dirname "$0")" && pwd)"
skill_src="$repo/skill"
[[ -d "$skill_src" ]] || { echo "skill/ not found next to install.sh"; exit 1; }

step() { printf "\033[36m[camclave]\033[0m %s\n" "$*"; }
warn() { printf "\033[33m[camclave]\033[0m %s\n" "$*"; }

# 1. Python deps
step "Installing Python dependencies (opencv-python, Pillow)..."
python_bin="${PYTHON:-python3}"
command -v "$python_bin" >/dev/null || { echo "Python 3.10+ not found"; exit 1; }
"$python_bin" -m pip install --user --upgrade opencv-python Pillow

# 2. Install skill into both agent skill dirs
install_skill() {
    local target_root="$1"
    local target="$target_root/camclave"
    mkdir -p "$target_root"
    if [[ -e "$target" || -L "$target" ]]; then
        warn "Existing $target removed."
        rm -rf "$target"
    fi
    if ln -s "$skill_src" "$target" 2>/dev/null; then
        step "Linked $target -> $skill_src"
    else
        warn "Symlink failed, copying."
        cp -R "$skill_src" "$target"
        step "Copied $skill_src -> $target"
    fi
}

install_skill "$HOME/.claude/skills"
install_skill "$HOME/.codex/skills"

# 3. Shim on PATH
bin_dir="$HOME/.local/bin"
mkdir -p "$bin_dir"
shim="$bin_dir/camclave"
cat > "$shim" <<EOF
#!/usr/bin/env bash
exec "$python_bin" "$skill_src/scripts/camclave.py" "\$@"
EOF
chmod +x "$shim"

case ":$PATH:" in
    *":$bin_dir:"*) step "$bin_dir already on PATH." ;;
    *) warn "Add this to your shell rc: export PATH=\"$bin_dir:\$PATH\"" ;;
esac

echo
step "installed. Try:  camclave start"
step "Then in Claude Code or Codex: 'use camclave to show me what I'm holding'."
