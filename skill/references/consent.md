# Consent model

The user, not the agent, initiates the camera session. There is no persistent "allow camera access" flag on disk; consent is per-session, time-limited, and visibly indicated.

## Lifecycle

1. **User runs `camclave start`** in a terminal.
   - The preview daemon process opens the camera.
   - An always-on-top red-bordered window appears with the label `● CAMERA ACTIVE`.
   - A `session.json` is written to `~/.camclave/` containing the daemon PID, device index, TTL (default 15 min, max 60 min), and start timestamp.
2. **The agent calls `camclave capture` or `camclave snapshots`.**
   - The CLI checks `session.json` exists, the PID is live, and the TTL hasn't expired. If any check fails, the call refuses.
3. **Session ends when any of these happen:**
   - The user closes the preview window.
   - The user runs `camclave stop`.
   - The TTL expires.
   - The user kills the daemon process by any other means.
4. **On end:**
   - `session.json` and IPC files are removed.
   - Captured PNGs in `~/.camclave/captures/` are deleted unless the session was started with `--keep`.

## What the agent must not do

- Tell the user "I'll start the camera now" and call `camclave start` itself. That is a consent violation. Always let the user be the one to type `camclave start`.
- Pre-fetch frames "just in case" before the user has asked for visual help.
- Increase the TTL silently or restart the session when it expires.
