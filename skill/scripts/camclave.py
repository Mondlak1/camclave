"""camclave CLI — the consent-gated entry point.

Subcommands:
    start             open the preview daemon (this is the consent action)
    status            show whether a session is active
    capture           one-shot frame grab (requires active session)
    snapshots         periodic snapshot mode (still frames, never video)
    snapshots-stop    cancel periodic mode early
    adjust            tweak camera properties (brightness, exposure, focus, ...)
    stop              kill the daemon and end the session
    devices           list probable camera indices

camclave never captures video. Every frame on disk is an explicit, on-demand
PNG. There is no streaming, no rolling buffer, no recording path.
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
    ADJUST_REQUEST,
    ADJUST_RESPONSE,
    CAPTURE_REQUEST,
    CAPTURE_RESPONSE,
    CAMCLAVE_DIR,
    MAX_TTL_SECONDS,
    SESSION_FILE,
    SNAPSHOT_CONFIG,
    active_session,
    clear_session,
    read_session,
)

# Friendly names of every property the daemon will accept. Kept in sync with
# ADJUST_PROPS in preview_daemon.py.
ADJUST_PROP_NAMES = [
    "brightness", "contrast", "saturation", "hue", "gain", "exposure",
    "focus", "zoom", "sharpness", "gamma",
    "auto_exposure", "auto_focus", "auto_wb", "wb_temperature",
]


def parse_duration(s: str) -> int:
    if s.isdigit():
        return int(s)
    total = 0
    for n, unit in re.findall(r"(\d+)\s*([smhSMH])", s):
        total += int(n) * {"s": 1, "m": 60, "h": 3600}[unit.lower()]
    if total == 0:
        raise SystemExit(f"camclave: could not parse duration {s!r}")
    return total


def cmd_start(args: argparse.Namespace) -> None:
    if active_session():
        print("camclave: a session is already active. Run `camclave stop` first.", file=sys.stderr)
        sys.exit(2)
    clear_session()
    ttl_s = parse_duration(args.ttl)
    if ttl_s > MAX_TTL_SECONDS:
        print(f"camclave: ttl capped to {MAX_TTL_SECONDS}s (hard max)", file=sys.stderr)
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
            "camclave: failed to start preview daemon. Is the camera in use by another app, "
            "or are opencv-python/Pillow missing? Try `pip install opencv-python pillow`.",
            file=sys.stderr,
        )
        sys.exit(3)
    print(f"camclave: preview started — device {s.device}, ttl {s.ttl_seconds}s, pid {s.pid}")
    print('a red-bordered "CAMERA ACTIVE" window is now visible. Close it (or run `camclave stop`) to end the session.')


def cmd_status(_args: argparse.Namespace) -> None:
    s = active_session()
    if not s:
        if SESSION_FILE.exists():
            clear_session()
            print("camclave: stale session file removed. No live daemon.")
        else:
            print("camclave: no active session.")
        return
    print(f"camclave: ACTIVE — device {s.device}, pid {s.pid}, {s.remaining_seconds}s remaining")
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
            "camclave: no active session. The user must run `camclave start` first "
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
    print("camclave: capture timed out — preview daemon may be stalled.", file=sys.stderr)
    sys.exit(5)


def cmd_snapshots(args: argparse.Namespace) -> None:
    s = active_session()
    if not s:
        print("camclave: no active session. Run `camclave start` first.", file=sys.stderr)
        sys.exit(4)
    every = max(1, parse_duration(args.every))
    duration = parse_duration(args.duration)
    out = Path(args.out).expanduser().resolve() if args.out else (CAMCLAVE_DIR / "latest.png")
    cfg = {"every": every, "until": time.time() + duration, "out_path": str(out)}
    SNAPSHOT_CONFIG.write_text(json.dumps(cfg))
    print(f"camclave: snapshot mode on — every {every}s for {duration}s, writing {out}")


def cmd_snapshots_stop(_args: argparse.Namespace) -> None:
    if SNAPSHOT_CONFIG.exists():
        SNAPSHOT_CONFIG.write_text(json.dumps({"disabled": True}))
        print("camclave: snapshot mode stopped.")
    else:
        print("camclave: snapshot mode wasn't active.")


def cmd_stop(_args: argparse.Namespace) -> None:
    s = read_session()
    if not s:
        print("camclave: no session to stop.")
        return
    keep = bool(s.keep)

    # Ask the daemon to exit gracefully so ITS cleanup handler runs and
    # deletes captures + the default snapshot. taskkill (no /F) on Windows
    # sends WM_CLOSE which our root.protocol("WM_DELETE_WINDOW", shutdown)
    # picks up. SIGTERM on Unix lets Python unwind through the `finally:
    # shutdown()` in run().
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(s.pid)], check=False, capture_output=True)
        else:
            os.kill(s.pid, 15)
    except Exception:
        pass

    # Wait up to 2.5s for the daemon to clean up on its own.
    from session import pid_alive
    deadline = time.time() + 2.5
    while time.time() < deadline:
        if not pid_alive(s.pid):
            break
        time.sleep(0.1)

    # Force-kill anything still alive
    if pid_alive(s.pid):
        try:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(s.pid), "/F"], check=False, capture_output=True)
            else:
                os.kill(s.pid, 9)
        except Exception:
            pass
        time.sleep(0.3)

    # Safety-net sweep in case the daemon was force-killed before its
    # shutdown() ran. Honors --keep just like the daemon does.
    if not keep:
        _sweep_camclave_dir()

    clear_session()
    print("camclave: stopped.")


def _sweep_camclave_dir() -> None:
    """Sweep ~/.camclave/captures/ and the default snapshot path.

    Safety net for `stop` — if the daemon got force-killed before its own
    shutdown() ran, this catches the leftover files. Only touches files
    inside ~/.camclave/ — never paths outside.
    """
    try:
        captures_dir = CAMCLAVE_DIR / "captures"
        if captures_dir.exists():
            for p in captures_dir.glob("*"):
                if p.is_file():
                    try:
                        p.unlink()
                    except Exception:
                        pass
    except Exception:
        pass
    default_snap = CAMCLAVE_DIR / "latest.png"
    if default_snap.exists():
        try:
            default_snap.unlink()
        except Exception:
            pass


def _send_adjust(request: dict) -> dict | None:
    try:
        ADJUST_RESPONSE.unlink()
    except FileNotFoundError:
        pass
    ADJUST_REQUEST.write_text(json.dumps(request))
    deadline = time.time() + 3
    while time.time() < deadline:
        if ADJUST_RESPONSE.exists():
            try:
                resp = json.loads(ADJUST_RESPONSE.read_text())
            except Exception:
                resp = None
            try:
                ADJUST_RESPONSE.unlink()
            except FileNotFoundError:
                pass
            return resp
        time.sleep(0.05)
    try:
        ADJUST_REQUEST.unlink()
    except FileNotFoundError:
        pass
    return None


def cmd_adjust(args: argparse.Namespace) -> None:
    s = active_session()
    if not s:
        print("camclave: no active session. Run `camclave start` first.", file=sys.stderr)
        sys.exit(4)

    if args.show:
        resp = _send_adjust({"show": True})
        if not resp:
            print("camclave: adjust timed out — daemon not responding.", file=sys.stderr)
            sys.exit(5)
        print("camclave: current camera properties (values are backend-dependent)")
        for name in ADJUST_PROP_NAMES:
            v = resp.get("applied", {}).get(name)
            print(f"  {name:<16} {v}")
        return

    settings: dict[str, float] = {}
    for name in ADJUST_PROP_NAMES:
        v = getattr(args, name, None)
        if v is not None:
            settings[name] = v
    if not settings:
        print(
            "camclave: nothing to adjust. Pass --show to read current values, or one or "
            "more property flags (e.g. --brightness 0.6 --exposure -7).",
            file=sys.stderr,
        )
        sys.exit(2)

    resp = _send_adjust({"set": settings})
    if not resp:
        print("camclave: adjust timed out — daemon not responding.", file=sys.stderr)
        sys.exit(5)
    applied = resp.get("applied", {})
    rejected = resp.get("rejected", [])
    for name, value in settings.items():
        actual = applied.get(name)
        if name in rejected or actual is None:
            print(f"  {name:<16} rejected by backend")
        else:
            note = "" if abs(actual - value) < 1e-3 else f"  (clipped from {value})"
            print(f"  {name:<16} -> {actual}{note}")


def cmd_devices(_args: argparse.Namespace) -> None:
    import cv2

    print("camclave: probing camera indices 0..5 (may briefly flash other cameras)")
    if os.name == "nt":
        backends = [("MSMF", cv2.CAP_MSMF), ("DSHOW", cv2.CAP_DSHOW)]
    else:
        backends = [("ANY", cv2.CAP_ANY)]
    for i in range(6):
        result = "—"
        for name, backend in backends:
            cap = cv2.VideoCapture(i, backend)
            opens = cap.isOpened()
            ok = False
            if opens:
                ok, _ = cap.read()
            cap.release()
            if ok:
                result = f"live via {name}"
                break
            if opens and result == "—":
                result = f"opens but no frame ({name})"
        print(f"  device {i}: {result}")


def main() -> None:
    ap = argparse.ArgumentParser(
        prog="camclave",
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
    p.add_argument("--out", help="optional explicit output path; default ~/.camclave/captures/")
    p.set_defaults(func=cmd_capture)

    p = sub.add_parser("snapshots", help="periodic snapshot mode")
    p.add_argument("--every", default="5s")
    p.add_argument("--duration", default="2m")
    p.add_argument("--out", help="snapshot output path (default ~/.camclave/latest.png)")
    p.set_defaults(func=cmd_snapshots)

    p = sub.add_parser("snapshots-stop", help="turn snapshot mode off early")
    p.set_defaults(func=cmd_snapshots_stop)

    p = sub.add_parser(
        "adjust",
        help="tweak camera properties (brightness, exposure, focus, etc.)",
        description=(
            "Adjust the live camera's properties. Values are backend-specific: most "
            "are 0..1, exposure is typically negative (-1 to -13) on Windows DSHOW, "
            "and auto-* toggles are 0=off / 1=on (DSHOW quirk: 0.25 = manual, 0.75 = auto)."
        ),
    )
    p.add_argument("--show", action="store_true", help="print current values for all properties")
    for name in ADJUST_PROP_NAMES:
        p.add_argument(f"--{name.replace('_', '-')}", dest=name, type=float, default=None)
    p.set_defaults(func=cmd_adjust)

    p = sub.add_parser("stop", help="kill the preview daemon and end the session")
    p.set_defaults(func=cmd_stop)

    p = sub.add_parser("devices", help="probe attached camera indices")
    p.set_defaults(func=cmd_devices)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
