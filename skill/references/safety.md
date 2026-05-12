# Safety rails (enforced by code)

These aren't suggestions — they're enforced by the CLI and daemon:

| Rail | Where enforced |
| --- | --- |
| **IPC requests are authenticated.** Every capture / snapshot / adjust request must carry the 32-hex-char session token from `~/.camclave/session.json` (mode 0o600). Mismatched or missing tokens are silently dropped — no response written, no flash, no audit entry. A foreign local process that lacks read access to session.json cannot forge a request. | `preview_daemon.py: _check_token`, `_consume_request`; `session.py: Session.token` |
| **IPC writes never follow symlinks.** Each IPC file write uses `safe_write_json` which unlinks the target if it's a symlink, then writes through a `.tmp` sibling and `os.replace`s it into place atomically. `O_NOFOLLOW` is added on POSIX. | `session.py: safe_write_json` |
| **IPC reads never follow symlinks.** `safe_read_json` returns None if the target is a symlink — daemon and CLI treat that as "no request". | `session.py: safe_read_json` |
| **`--out` paths are sanity-checked.** `..` segments in the user-provided path are rejected; if the resolved parent directory is itself a symlink, the write is rejected. Out-of-`~/.camclave/` paths are still allowed (documented policy) — just guarded. | `camclave.py: _safe_out_path` |
| **`cv2.imwrite` return values are checked.** A `False` return (disk full / permission / bad path) is reported back to the CLI as a structured `{"error": "..."}` response instead of a fake path. | `preview_daemon.py: handle_capture_request`, `handle_snapshot` |
| **JSON IPC is schema-validated.** `validate_payload` rejects payloads that don't match the expected type spec. | `session.py: validate_payload` (used by `read_session`) |
| **Snapshot rate is clamped to ≥2s.** Matches what the agent contract has always claimed; the CLI prints a notice if it had to clamp. | `camclave.py: cmd_snapshots` |
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
| Captures land only in `~/.camclave/captures/` (when no `--out` given) | default in `handle_capture_request` |
| Stale captures from a previous unclean exit are swept at `start` | `preview_daemon.py: _sweep_captures_dir()` |
| On `stop`, **every file** in `~/.camclave/captures/` is deleted (unless `--keep`) | `preview_daemon.py: shutdown()` |
| On `stop`, default snapshot file `~/.camclave/latest.png` is deleted | `preview_daemon.py: _sweep_captures_dir()` + tracked `snapshot_out_paths` |
| On `stop`, any snapshot `--out` path **inside** `~/.camclave/` is deleted; paths **outside** (e.g. `/tmp/foo.png`) are left alone | `preview_daemon.py: shutdown()` — path is resolved and checked against `CAMCLAVE_DIR` |
| `capture --out PATH` files are NEVER auto-deleted | by design — you explicitly asked for that path |
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
