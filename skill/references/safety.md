# Safety rails (enforced by code)

These aren't suggestions — they're enforced by the CLI and daemon:

| Rail | Where enforced |
| --- | --- |
| Capture refuses without an active session | `camclave.py: cmd_capture` checks `active_session()` |
| Capture refuses if daemon PID is dead | `session.py: active_session()` -> `pid_alive()` |
| Capture refuses if TTL expired | `session.py: Session.expired` |
| TTL hard cap of 60 min | `session.py: MAX_TTL_SECONDS`, clamped in `camclave.py` |
| Every capture flashes the preview | `preview_daemon.py: handle_capture_request` -> `state["flash_until"]` |
| Every capture beeps (unless `--no-sound`) | `preview_daemon.py: beep()` |
| Preview window is always-on-top | `root.attributes("-topmost", True)` |
| Window has red border + "CAMERA ACTIVE" label | `preview_daemon.py` |
| Captures land only in `~/.camclave/captures/` | default in `handle_capture_request` |
| Captures auto-deleted on `stop` | `preview_daemon.py: shutdown()` (unless `--keep`) |
| Zero network code | grep the repo for `urllib`/`requests`/`http`/`socket` — none |

## Things deliberately out of scope (v1)

- Audio capture
- Screen capture
- Multiple simultaneous cameras
- Remote / headless mode

If a future version adds any of these, it requires a separate consent action.
