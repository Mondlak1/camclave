"""lookhere CLI — the consent-gated entry point.

Subcommands:
    start             open the preview daemon (this is the consent action)
    status            show whether a session is active
    capture           one-shot frame grab (requires active session)
    snapshots         periodic snapshot mode
    snapshots-stop    cancel periodic mode early
    stop              kill the daemon and end the session
    devices           list probable camera indices
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from session import (  # noqa: E402
    CAPTURE_REQUEST,
    CAPTURE_RESPONSE,
    LOOKHERE_DIR,
    MAX_TTL_SECONDS,
    SESSION_FILE,
    SNAPSHOT_CONFIG,
    active_session,
    clear_session,
    read_session,
)


def parse_duration(s: str) -> int:
    if s.isdigit():
        return int(s)
    total = 0
    for n, unit in re.findall(r"(\d+)\s*([smhSMH])", s):
        total += int(n) * {"s": 1, "m": 60, "h": 3600}[unit.lower()]
    if total == 0:
        raise SystemExit(f"lookhere: could not parse duration {s!r}")
    return total


def cmd_start(args: argparse.Namespace) -> None:
    if active_session():
        print("lookhere: a session is already active. Run `lookhere stop` first.", file=sys.stderr)
        sys.exit(2)
    clear_session()
    ttl_s = parse_duration(args.ttl)
    if ttl_s > MAX_TTL_SECONDS:
        print(f"lookhere: ttl capped to {MAX_TTL_SECONDS}s (hard max)", file=sys.stderr)
        ttl_s = MAX_TTL_SECONDS

    daemon = HERE / "preview_daemon.py"
    cmd = [sys.executable, str(daemon), "--device", str(args.device), "--ttl", str(ttl_s)]
    if args.no_sound:
        cmd.append("--no-sound")
    if args.keep:
        cmd.append("--keep")

    if os.name == "nt":
        DETACHED_PROCESS = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        subprocess.Popen(cmd, creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP, close_fds=True)
    else:
        subprocess.Popen(cmd, start_new_session=True, close_fds=True)

    for _ in range(60):
        if active_session():
            break
        time.sleep(0.1)
    s = active_session()
    if not s:
        print(
            "lookhere: failed to start preview daemon. Is the camera in use by another app, "
            "or are opencv-python/Pillow missing? Try `pip install opencv-python pillow`.",
            file=sys.stderr,
        )
        sys.exit(3)
    print(f"lookhere: preview started — device {s.device}, ttl {s.ttl_seconds}s, pid {s.pid}")
    print('a red-bordered "CAMERA ACTIVE" window is now visible. Close it (or run `lookhere stop`) to end the session.')


def cmd_status(_args: argparse.Namespace) -> None:
    s = active_session()
    if not s:
        if SESSION_FILE.exists():
            clear_session()
            print("lookhere: stale session file removed. No live daemon.")
        else:
            print("lookhere: no active session.")
        return
    print(f"lookhere: ACTIVE — device {s.device}, pid {s.pid}, {s.remaining_seconds}s remaining")
    if SNAPSHOT_CONFIG.exists():
        try:
            cfg = json.loads(SNAPSHOT_CONFIG.read_text())
            remaining = max(0, int(cfg.get("until", 0) - time.time()))
            print(
                f"  snapshot mode: every {cfg.get('every')}s, {remaining}s remaining, "
                f"writing to {cfg.get('out_path')}"
            )
        except Exception:
            pass


def cmd_capture(args: argparse.Namespace) -> None:
    s = active_session()
    if not s:
        print(
            "lookhere: no active session. The user must run `lookhere start` first "
            "(this is the consent action).",
            file=sys.stderr,
        )
        sys.exit(4)
    try:
        CAPTURE_RESPONSE.unlink()
    except FileNotFoundError:
        pass
    req: dict[str, str] = {}
    if args.out:
        req["out_path"] = str(Path(args.out).expanduser().resolve())
    CAPTURE_REQUEST.write_text(json.dumps(req))
    deadline = time.time() + 5
    while time.time() < deadline:
        if CAPTURE_RESPONSE.exists():
            try:
                resp = json.loads(CAPTURE_RESPONSE.read_text())
            except Exception:
                resp = None
            try:
                CAPTURE_RESPONSE.unlink()
            except FileNotFoundError:
                pass
            if resp and resp.get("path"):
                print(resp["path"])
                return
        time.sleep(0.05)
    try:
        CAPTURE_REQUEST.unlink()
    except FileNotFoundError:
        pass
    print("lookhere: capture timed out — preview daemon may be stalled.", file=sys.stderr)
    sys.exit(5)


def cmd_snapshots(args: argparse.Namespace) -> None:
    s = active_session()
    if not s:
        print("lookhere: no active session. Run `lookhere start` first.", file=sys.stderr)
        sys.exit(4)
    every = max(1, parse_duration(args.every))
    duration = parse_duration(args.duration)
    out = Path(args.out).expanduser().resolve() if args.out else (LOOKHERE_DIR / "latest.png")
    cfg = {"every": every, "until": time.time() + duration, "out_path": str(out)}
    SNAPSHOT_CONFIG.write_text(json.dumps(cfg))
    print(f"lookhere: snapshot mode on — every {every}s for {duration}s, writing {out}")


def cmd_snapshots_stop(_args: argparse.Namespace) -> None:
    if SNAPSHOT_CONFIG.exists():
        SNAPSHOT_CONFIG.write_text(json.dumps({"disabled": True}))
        print("lookhere: snapshot mode stopped.")
    else:
        print("lookhere: snapshot mode wasn't active.")


def cmd_stop(_args: argparse.Namespace) -> None:
    s = read_session()
    if not s:
        print("lookhere: no session to stop.")
        return
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(s.pid), "/F"], check=False, capture_output=True)
        else:
            os.kill(s.pid, 15)
    except Exception:
        pass
    time.sleep(0.5)
    clear_session()
    print("lookhere: stopped.")


def cmd_devices(_args: argparse.Namespace) -> None:
    import cv2

    print("lookhere: probing camera indices 0..5 (may briefly flash other cameras)")
    for i in range(6):
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW) if os.name == "nt" else cv2.VideoCapture(i)
        opens = cap.isOpened()
        ok = False
        if opens:
            ok, _ = cap.read()
        cap.release()
        status = "live" if ok else ("opens but no frame" if opens else "—")
        print(f"  device {i}: {status}")


def main() -> None:
    ap = argparse.ArgumentParser(
        prog="lookhere",
        description="Consent-gated webcam access for Claude Code + Codex CLI.",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("start", help="open the preview window and create a session (consent action)")
    p.add_argument("--device", type=int, default=0)
    p.add_argument("--ttl", default="15m", help="session lifetime e.g. 5m, 30m, 1h (max 60m)")
    p.add_argument("--no-sound", action="store_true")
    p.add_argument("--keep", action="store_true", help="don't delete captured PNGs on stop")
    p.set_defaults(func=cmd_start)

    p = sub.add_parser("status", help="show whether a session is active")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("capture", help="grab one frame; prints absolute PNG path on stdout")
    p.add_argument("--out", help="optional explicit output path; default ~/.lookhere/captures/")
    p.set_defaults(func=cmd_capture)

    p = sub.add_parser("snapshots", help="periodic snapshot mode")
    p.add_argument("--every", default="5s")
    p.add_argument("--duration", default="2m")
    p.add_argument("--out", help="snapshot output path (default ~/.lookhere/latest.png)")
    p.set_defaults(func=cmd_snapshots)

    p = sub.add_parser("snapshots-stop", help="turn snapshot mode off early")
    p.set_defaults(func=cmd_snapshots_stop)

    p = sub.add_parser("stop", help="kill the preview daemon and end the session")
    p.set_defaults(func=cmd_stop)

    p = sub.add_parser("devices", help="probe attached camera indices")
    p.set_defaults(func=cmd_devices)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
