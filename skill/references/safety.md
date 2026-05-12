# Safety rails (enforced by code)

These aren't suggestions — they're enforced by the CLI and daemon:

| Rail | Where enforced |
| --- | --- |
| **No video capture, ever.** `cv2.VideoWriter` is never instantiated; no `.mp4`/`.avi`/`.mkv`/`.webm` writer exists in the codebase. Only `cv2.imwrite` of individual PNG/JPG frames triggered by an explicit request. | `preview_daemon.py` — grep the repo for `VideoWriter` |
| **No continuous frame storage.** The daemon does not write a rolling jpg or ring buffer to disk. Frames only land on disk when `capture` or `snapshots` requests one. | `preview_daemon.py: loop()` — no per-frame `imwrite` |
| Capture refuses without an active session | `camclave.py: cmd_capture` checks `active_session()` |
| Capture refuses if daemon PID is dead | `session.py: active_session()` -> `pid_alive()` |
| Capture refuses if TTL expired | `session.py: Session.expired` |
| `adjust` refuses without an active session | `camclave.py: cmd_adjust` checks `active_session()` |
| TTL hard cap of 60 min | `session.py: MAX_TTL_SECONDS`, clamped in `camclave.py` |
| Every capture flashes the preview | `preview_daemon.py: handle_capture_request` -> `state["flash_until"]` |
| Every capture beeps (unless `--no-sound`) | `preview_daemon.py: beep()` |
| Preview window is always-on-top | `root.attributes("-topmost", True)` |
| Window has red border + "CAMERA ACTIVE" label | `preview_daemon.py` |
| Captures land only in `~/.camclave/captures/` | default in `handle_capture_request` |
| Captures auto-deleted on `stop` | `preview_daemon.py: shutdown()` (unless `--keep`) |
| Zero network code | grep the repo for `urllib`/`requests`/`http`/`socket` — none |

## What `adjust` can and can't do

`adjust` tweaks the live camera's properties (brightness, exposure, focus, etc.) via OpenCV's `cap.set()`. It cannot:
- enable video recording (no recording path exists)
- bypass the consent gate (it checks `active_session()` like every other command)
- read or write any file outside `~/.camclave/`
- affect the camera after the daemon exits (settings revert when `cap.release()` is called on shutdown)

## Things deliberately out of scope

- **Video capture** — no `cv2.VideoWriter` anywhere; never will be in this skill.
- **Audio capture** — the daemon never opens an audio device.
- **Screen capture** — the daemon only opens `cv2.VideoCapture(<webcam-index>)`.
- Multiple simultaneous cameras
- Remote / headless mode

If a future version adds any of these, it requires a separate consent action and a separate codepath that re-derives the safety rails above. They would not silently extend the existing camclave session.
