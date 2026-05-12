---
name: camclave
description: Consent-gated webcam access so the agent can see a single still frame from the user's camera while the user watches a live preview. NO VIDEO CAPTURE — every frame on disk is an explicit, on-demand PNG. Use for hardware testing, OCR, plant logs, posture coaching, instrument reading. Includes `adjust` for tweaking camera properties (brightness, exposure, focus) live.
trigger: /camclave
license: MIT
---

# camclave

`camclave` lets you see **single still frames** from the user's webcam. The user must have explicitly run `camclave start` to consent to this session; otherwise capture refuses.

**There is no video capture.** Every frame that lands on disk is the result of an explicit `capture` or scheduled `snapshots` write. There is no rolling buffer, no continuous recording path, no streaming. The daemon never instantiates `cv2.VideoWriter` and never writes any video container.

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

**To adjust camera properties** (e.g. dim breadboard, glare on an LCD, autofocus hunting on a small target):

```
camclave adjust --show                              # read current values first
camclave adjust --brightness 0.7 --exposure -5
camclave adjust --auto-focus 0 --focus 120          # disable autofocus and pin focus
```

Supported: `brightness`, `contrast`, `saturation`, `hue`, `gain`, `exposure`, `focus`, `zoom`, `sharpness`, `gamma`, `auto_exposure`, `auto_focus`, `auto_wb`, `wb_temperature`. Values are backend-dependent — most are 0..1; exposure is usually negative on Windows DSHOW; auto-* toggles are 0=off / 1=on (DSHOW quirk: 0.25 = manual, 0.75 = auto). The CLI reports what the camera actually accepted vs. what you asked for.

**Other:**

```
camclave devices   # probe camera indices if device 0 isn't right
```

## Rules the agent must follow

1. **Never call `capture` without explaining first.** Say what you're about to look for ("I'll grab one frame to check the LED on D5") so the user can frame the shot.
2. **One frame at a time, on demand. Never burst.** Don't loop `capture` to simulate a video stream. If you need periodic visibility, use `snapshots` with a sensible interval (>=2s).
3. **Respect the TTL.** If status shows the session is nearly expired, finish up rather than start a long task.
4. **No upload.** Don't send the captured PNG to any remote service unless the user explicitly asks.
5. **Honor `--no-sound` and the user's window.** Don't try to suppress flashes or move the preview window.
6. **Try `adjust --show` before changing anything.** If the first frame is too dark / blurry, prefer one targeted property tweak (e.g. raise `brightness` or disable `auto_focus`) over taking many bad frames.

See `references/consent.md` and `references/safety.md` for the full contract, and `references/use-cases.md` for patterns.
