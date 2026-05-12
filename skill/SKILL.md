---
name: camclave
description: Consent-gated webcam access so the agent can see frames from the user's camera while the user watches a live, always-on-top preview. Use for hardware testing, OCR, plant logs, posture coaching, instrument reading, etc. Captures only happen on demand; every capture flashes the preview.
trigger: /camclave
license: MIT
---

# camclave

`camclave` lets you see a single still frame from the user's webcam — never a video stream. The user must have explicitly run `camclave start` to consent to this session; otherwise capture refuses.

## How to use it (agent-side)

**Before calling anything, check the session is active:**

```
camclave status
```

If no session is active, do **not** retry. Tell the user: "I need to see your camera. Please run `camclave start` in another terminal, then ask me again." That is the consent contract — the agent never instructs the user to start the session as part of an in-flow action; the user must initiate it.

**To grab one frame** (most common):

```
camclave capture
```

Prints an absolute PNG path on stdout. Read the PNG with your image-reading tool. The preview window flashes white and beeps the moment the frame is captured.

**To watch over time** (e.g. 3D print baby-sitting, plant logging):

```
camclave snapshots --every 30s --duration 10m --out /tmp/latest.png
```

The daemon overwrites `--out` on every interval. Re-read the file when you want a fresh look. Stop early with `camclave snapshots-stop`.

**Other:**

```
camclave devices   # probe camera indices if device 0 isn't right
```

## Rules the agent must follow

1. **Never call `capture` without explaining first.** Say what you're about to look for ("I'll grab one frame to check the LED on D5") so the user can frame the shot.
2. **One frame at a time, on demand.** Don't loop `capture` to fake a video stream. If you need periodic visibility, use `snapshots` with a sensible interval.
3. **Respect the TTL.** If status shows the session is nearly expired, finish up rather than start a long task.
4. **No upload.** Don't send the captured PNG to any remote service unless the user explicitly asks.
5. **Honor `--no-sound` and the user's window.** Don't try to suppress flashes or move the preview window.

See `references/consent.md` and `references/safety.md` for the full contract, and `references/use-cases.md` for patterns.
