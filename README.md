<div align="center">

# `camclave`

### Connect your camera to an AI agent. Solve hardware in real life.

**A consent-gated webcam plugin for [Claude Code](https://claude.ai/code) and [Codex CLI](https://github.com/openai/codex).** Point your camera at a breadboard, a 3D print, an instrument, a paper schematic — and your AI agent can actually see it. One still frame at a time, only while a visible red "CAMERA ACTIVE" window is on your screen.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org)
[![Works with Claude Code](https://img.shields.io/badge/Claude%20Code-skill-7c3aed.svg)](https://claude.ai/code)
[![Works with Codex CLI](https://img.shields.io/badge/Codex%20CLI-skill-10a37f.svg)](https://github.com/openai/codex)
[![Hardware automation](https://img.shields.io/badge/use-hardware%20automation-ff2a2a.svg)](#what-you-can-actually-do-with-this)

```bash
camclave start            # ← consent action. Red "CAMERA ACTIVE" window appears.
# now ask Claude Code or Codex:
#   "read the multimeter on my bench"
#   "is the LED on D5 lit?"
#   "watch my 3D print and ping me if the first layer fails"
camclave stop             # camera off. Captures wiped.
```

</div>

---

## The problem

Most of the time you want help from an AI agent, the agent already has everything it needs — your files, your terminal, your codebase. But the moment your problem is **physical** — wiring, soldering, a stuck print, an instrument reading, a label, a handwritten note — the loop breaks. You're snapping phone photos one by one, uploading them, describing what's in them. The agent can't *look*.

`camclave` closes that loop. The agent calls a CLI, gets back a PNG path, reads the PNG with its image tool, and answers. You see exactly what it sees, on screen, the moment it sees it.

## How it works

```
┌──────────────────────────────────┐   ┌──────────────────────────┐
│ Terminal (Claude Code / Codex)   │   │ Preview window (always   │
│   → camclave capture             │   │ on top, red border,      │
│   ← /path/to/frame.png           │   │ "● CAMERA ACTIVE")       │
│   → agent reads PNG, answers     │ ◄─┤  flashes white +         │
└──────────────────────────────────┘   │  beeps on every capture  │
                                       └──────────────────────────┘
```

The CLI command name **is the consent signal.** There is no remembered "allow camera" toggle. The camera is off until you type `camclave start`. The agent never starts the session itself.

### No video capture. Ever.

`camclave` only ever writes **single still frames** to disk, and only when `capture` or `snapshots` is explicitly invoked. The daemon never instantiates `cv2.VideoWriter`. There is no rolling buffer, no continuous recording path, no `.mp4` / `.avi` / `.mkv` / `.webm` writer anywhere in this codebase. Grep for `VideoWriter` — zero hits. The "live" preview window renders frames straight to Tk and discards them; nothing about the on-screen preview persists to disk.

If a future version ever adds video, it will be in a separately-named tool with its own consent action — not by extending an existing `camclave start` session.

## Install

**Windows:**
```powershell
git clone https://github.com/Mondlak1/camclave.git
cd camclave
pwsh ./install.ps1
```

**macOS / Linux:**
```bash
git clone https://github.com/Mondlak1/camclave.git
cd camclave
bash ./install.sh
```

The installer:
1. `pip install --user opencv-python Pillow`
2. Symlinks `skill/` into **both** `~/.claude/skills/camclave/` and `~/.codex/skills/camclave/` (copy fallback on Windows without symlink privilege).
3. Puts a `camclave` shim on your PATH.

## CLI surface

| Command | What it does |
| --- | --- |
| `camclave start [--device 0] [--ttl 15m] [--no-sound] [--keep]` | **Consent action.** Opens the preview daemon. Default TTL 15 min, hard cap 60 min. |
| `camclave status` | Active? How much TTL left? Is snapshot mode running? |
| `camclave capture [--out PATH]` | Grabs one frame; prints absolute PNG path on stdout. Preview flashes. |
| `camclave snapshots --every 30s --duration 10m [--out PATH]` | Periodic mode for long-running tasks. Overwrites one file. Still frames, never video. |
| `camclave snapshots-stop` | Cancel snapshot mode early. |
| `camclave adjust [--show] [--brightness 0.6] [--exposure -5] [--focus 120] ...` | Tweak the live camera's properties: brightness, contrast, saturation, hue, gain, exposure, focus, zoom, sharpness, gamma, auto_exposure, auto_focus, auto_wb, wb_temperature. `--show` prints current values. The CLI reports what the camera accepted vs. what you asked for. |
| `camclave stop` | Kill the daemon. Captures auto-deleted unless `--keep` was set. |
| `camclave devices [--preview]` | Probe camera indices 0..5, reporting which OpenCV backend works. With `--preview`, also saves one PNG per working camera to `~/.camclave/device-<N>.png` so you can visually identify which is the laptop integrated cam vs. the USB webcam vs. a virtual cam, then `camclave start --device <N>`. |

## What you can actually do with this

`camclave` is built for **hardware automation through AI** — handing the agent eyes for the parts of your workflow that aren't text:

- 🔌 **Breadboard debugging** — *"Is the LED on D5 lit? Does the current draw on the multimeter look right? Trace the path of the red jumper."*
- 📟 **Instrument reading** — multimeters, oscilloscopes, kitchen scales, smart-meter LCDs, power-supply displays. The agent OCRs the value and logs it for you.
- 🖨️ **3D-print monitoring** — `snapshots --every 30s --duration 4h`, agent pings you when the first layer fails or stringing starts.
- 🔬 **Soldering inspection** — close-up shots, agent flags bridges, tombstoning, cold joints, missing pads.
- 📓 **Lab-notebook digitization** — hold a handwritten page up, agent transcribes to markdown with tables intact.
- 🪴 **Plant log** — one snapshot per day, agent tracks leaf-color drift and flags wilting before you notice.
- 🪑 **Posture / ergonomics coaching** — `snapshots --every 2m --duration 1h`, agent nudges when you slouch.
- 🎥 **Pre-call setup check** — *"is my ring light on? is my camera framed correctly?"*
- 📦 **Package label capture** — agent files contents and tracking numbers into a spreadsheet.
- 🤝 **Pair-programming with paper** — point the camera at a circuit diagram while you code firmware in the same chat.
- 🤖 **Robotics & maker QA** — verify servo positions, gripper alignment, sensor wiring; the agent reads visual state into the loop.
- 🧪 **Bench-science assistant** — read the gel, count colonies on a plate, log microscope eyepiece images.

## Safety — in one screen

- **No video capture, period.** `cv2.VideoWriter` is never instantiated. No `.mp4`/`.avi`/`.mkv`/`.webm` writer exists. Only single-frame PNG/JPG writes triggered by explicit `capture` or `snapshots` calls.
- **No continuous frame storage.** The daemon does not write a rolling jpg or ring buffer. Frames only hit disk when you ask for one.
- **Zero network code.** Frames never leave your machine. Grep the repo for `urllib`/`requests`/`http`/`socket` — none.
- **No persistent consent.** Camera is off until you type `camclave start`.
- **Default TTL 15 min, hard cap 60 min.** After expiry, capture refuses; the daemon shuts itself down.
- **Always-on-top red window** labelled **● CAMERA ACTIVE** while the session is live.
- **Every capture flashes white** in the preview window + system beep. The audible beep is suppressible (`--no-sound`); the flash is not.
- **Captures wiped on stop** unless you explicitly pass `--keep`:
  - Default captures (`~/.camclave/captures/frame-*.png`) → deleted.
  - Default snapshot (`~/.camclave/latest.png`) → deleted.
  - Snapshot `--out` files that live **inside** `~/.camclave/` → deleted.
  - Files you explicitly pointed **outside** `~/.camclave/` (e.g. `capture --out /tmp/foo.png`, `snapshots --out /tmp/print.png`) → **kept**, because you asked for that path. You own them.
  - A crashed daemon's leftovers are swept the next time you `start`.

Full contracts: [`skill/references/consent.md`](skill/references/consent.md) and [`skill/references/safety.md`](skill/references/safety.md).

## Why a CLI tool instead of an MCP server / browser thing?

Because the consent gate has to be **on the user's terminal**, not negotiated over a transport. Typing the word `camclave` into your own shell is unambiguous. An MCP-mediated camera tool would lose that property — the agent could invoke it on its own.

A bonus: this works identically in Claude Code, Codex CLI, and any future agent that can shell out and read a PNG. One install, two agents.

## Uninstall

```powershell
pwsh ./uninstall.ps1   # Windows
bash ./uninstall.sh    # macOS / Linux
```

Removes both skill installs and the PATH shim. Leaves `~/.camclave/` so you can inspect any captures you marked `--keep`.

## Contributing

PRs welcome — especially additional safety rails, OS-specific camera quirks, and richer agent reference docs. Open an issue first for non-trivial features so we keep the surface small.

## License

MIT. See [`LICENSE`](LICENSE).

---

<sub>**Tags:** AI agent camera, Claude Code webcam plugin, Codex CLI camera skill, hardware automation, LLM computer vision, agent vision tool, breadboard debugging AI, instrument reading OCR, 3D print monitoring, agentic hardware testing.</sub>
