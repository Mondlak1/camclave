<div align="center">

# `lookhere`

### give Claude Code and Codex CLI your webcam — on your terms

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org)
[![Works with Claude Code](https://img.shields.io/badge/Claude%20Code-skill-7c3aed.svg)](https://claude.ai/code)
[![Works with Codex CLI](https://img.shields.io/badge/Codex%20CLI-skill-10a37f.svg)](https://github.com/openai/codex)
[![Status: v0.1](https://img.shields.io/badge/status-v0.1-orange.svg)](#)

**Type `lookhere start` → a red "CAMERA ACTIVE" window pops up. From now until you close it, the agent can grab one still frame at a time. Every frame flashes the preview. Close the window or run `lookhere stop` and the camera is gone.**

</div>

---

## What is this?

A tiny dual-install skill plugin for [Claude Code](https://claude.ai/code) and [Codex CLI](https://github.com/openai/codex). Once you give consent (by typing `lookhere start`), the agent can call `lookhere capture` and read back a PNG of what your webcam sees. The agent never gets a video stream — only single frames you can correlate with the live preview on your screen.

The CLI command name **is** the consent signal. There is no "remember this allow" toggle. Camera stays off until you ask.

## Why?

Because most useful "show me your work" tasks aren't typing problems — they're *physical* problems. Showing the agent your breadboard, your multimeter, your handwritten notes, your plant, your posture. Built-in screen-share is way too much, and uploading photos one by one is friction. `lookhere` is the smallest possible surface for "the agent can see what I'm pointing at, but only when I say so."

## Quick install (Windows)

```powershell
git clone https://github.com/Mondlak1/lookhere.git
cd lookhere
pwsh ./install.ps1
```

## Quick install (macOS / Linux)

```bash
git clone https://github.com/Mondlak1/lookhere.git
cd lookhere
bash ./install.sh
```

The installer:
1. `pip install --user opencv-python Pillow`
2. Symlinks `skill/` into `~/.claude/skills/lookhere/` **and** `~/.codex/skills/lookhere/` (copy fallback on Windows without symlink privilege).
3. Writes a `lookhere` shim onto your PATH (`~/.local/bin/lookhere` or `%USERPROFILE%\.lookhere\bin\lookhere.cmd`).

## How to use it

```bash
# 1. Open a terminal and consent.
lookhere start

#     → a red "CAMERA ACTIVE" window appears, top-most, with a 15-minute timer.

# 2. In your Claude Code or Codex session, ask away:
#     "Read the multimeter on my desk"
#     "Is the LED on D5 lit?"
#     "Transcribe my handwritten note"

# 3. Done? Close the window or:
lookhere stop
```

### Subcommands

| Command | What it does |
| --- | --- |
| `lookhere start [--device 0] [--ttl 15m] [--no-sound] [--keep]` | Opens the preview daemon. **This is the consent action.** |
| `lookhere status` | Shows whether a session is active and how much TTL is left. |
| `lookhere capture [--out PATH]` | Grabs one frame, prints absolute PNG path. The preview flashes. |
| `lookhere snapshots --every 30s --duration 10m [--out PATH]` | Writes a fresh PNG every interval; agent re-reads on demand. |
| `lookhere snapshots-stop` | Cancel snapshot mode early. |
| `lookhere stop` | Kill the daemon, delete captures (unless `--keep` was set at start). |
| `lookhere devices` | Probe camera indices 0..5. |

## What you can actually do with this

> Pick a vibe.

- 🔌 **Breadboard buddy** — *"Is the LED on D5 lit? Does the current draw on the multimeter look right?"*
- 📟 **Instrument reader** — multimeters, oscilloscopes, kitchen scales, smart-meter LCDs. The agent OCRs the value and logs it.
- 🖨️ **3D-print babysitter** — `snapshots --every 30s --duration 4h`. The agent pings you when the first layer fails or a stringy mess starts.
- 🔬 **Soldering inspector** — close-up shots, agent flags bridges, tombstoning, cold joints.
- 📓 **Lab-notebook digitizer** — hold up a page, agent transcribes to markdown with tables intact.
- 🪴 **Plant log** — one snapshot per day, agent tracks leaf-color drift and flags wilting.
- 🪑 **Posture coach** — `snapshots --every 2m --duration 1h`, agent nudges when you slouch.
- 🎥 **Setup verifier** — *"is my ring light on?"*, *"is my camera framed correctly for the call?"*
- 📦 **Package label capture** — agent files contents/tracking-numbers into a spreadsheet.
- 🤝 **Pair-programming with paper** — point the camera at a circuit diagram while you code firmware in the same chat.

## Safety in one screen

- Zero network code. Frames never leave your machine.
- Camera is off until you type `lookhere start`. There is no remembered consent.
- Default TTL is **15 minutes**; the hard cap is 60.
- Always-on-top red window labelled **CAMERA ACTIVE** while the session is live.
- Every capture **flashes white** in the preview + system beep (suppressible with `--no-sound`, the flash is not).
- Captures live in `~/.lookhere/captures/` and are wiped on `stop` unless you pass `--keep`.

Full details: [`skill/references/safety.md`](skill/references/safety.md) and [`skill/references/consent.md`](skill/references/consent.md).

## Uninstall

```powershell
pwsh ./uninstall.ps1   # Windows
bash ./uninstall.sh    # macOS / Linux
```

Removes the skill symlinks/copies and the PATH shim. Leaves `~/.lookhere/` so you can inspect any captures you kept; delete it manually if you don't want it.

## Contributing

PRs welcome — especially additional safety rails, OS-specific camera quirks, and richer agent reference docs. Open an issue first if you want to add a non-trivial feature so we can keep the surface small.

## License

MIT. See [`LICENSE`](LICENSE).
