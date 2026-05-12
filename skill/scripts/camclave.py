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
    AUDIT_LOG,
    CAPTURE_REQUEST,
    CAPTURE_RESPONSE,
    CAMCLAVE_DIR,
    DAEMON_LOG,
    MAX_TTL_SECONDS,
    SESSION_FILE,
    SNAPSHOT_CONFIG,
    active_session,
    clear_session,
    read_session,
    safe_read_json,
    safe_write_json,
)


def _safe_out_path(raw: str) -> Path:
    """Reject obviously-abusive --out values, otherwise resolve.

    Keeps the documented policy that paths outside ~/.camclave/ are
    allowed (so `capture --out /tmp/foo.png` still works), but blocks
    `..` segments and writes through symlinked parents.
    """
    expanded = os.path.expanduser(raw)
    # Reject `..` in the user-provided string; resolve() would normalize
    # it silently, but the intent is suspicious — refuse explicitly.
    if ".." in expanded.replace("\\", "/").split("/"):
        raise SystemExit(f"camclave: --out rejected — '..' segments not allowed: {raw!r}")
    p = Path(expanded).resolve()
    # If the immediate parent is a symlink, refuse — defense against
    # parent-dir symlink swap targeting attacker-chosen directories.
    if p.parent.is_symlink():
        raise SystemExit(f"camclave: --out rejected — parent directory is a symlink: {p.parent}")
    return p

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

    # Reset the daemon log; the DAEMON itself redirects its stderr/stdout to
    # this file (from inside __main__) so the redirection doesn't fight with
    # the Windows DETACHED_PROCESS flag.
    CAMCLAVE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        DAEMON_LOG.unlink()
    except FileNotFoundError:
        pass

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
            "camclave: failed to start preview daemon.",
            file=sys.stderr,
        )
        try:
            tail = DAEMON_LOG.read_text(errors="replace").splitlines()[-30:]
            if tail:
                print("--- daemon log (last 30 lines) ---", file=sys.stderr)
                for line in tail:
                    print(line, file=sys.stderr)
                print("--- end daemon log ---", file=sys.stderr)
        except Exception:
            pass
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

    # Show the last 5 captures from this session's audit log
    if AUDIT_LOG.exists():
        try:
            lines = AUDIT_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            lines = []
        captures = [json.loads(L) for L in lines[-50:] if L.strip().startswith("{")]
        captures = [c for c in captures if c.get("kind") == "capture"][-5:]
        if captures:
            print("\n  last captures:")
            for c in captures:
                ts = time.strftime("%H:%M:%S", time.localtime(c.get("ts", 0)))
                reason = c.get("reason") or "(no reason given)"
                print(f"    {ts}  {reason}")
                print(f"             -> {c.get('path')}")


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
    req: dict = {"token": s.token}
    if args.out:
        req["out_path"] = str(_safe_out_path(args.out))
    if args.reason:
        # Trim to a reasonable length so a wall of text can't crowd out the
        # preview window. The reason is informational, not security-critical.
        req["reason"] = args.reason.strip()[:120]
    safe_write_json(CAPTURE_REQUEST, req)
    deadline = time.time() + 5
    while time.time() < deadline:
        resp = safe_read_json(CAPTURE_RESPONSE)
        if resp is not None:
            try:
                CAPTURE_RESPONSE.unlink()
            except FileNotFoundError:
                pass
            if resp.get("error"):
                print(f"camclave: capture failed — {resp['error']}", file=sys.stderr)
                sys.exit(6)
            if resp.get("path"):
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
    requested = parse_duration(args.every)
    every = max(2, requested)
    if every != requested:
        print(
            f"camclave: snapshot rate clamped to {every}s (minimum is 2s — see "
            "skill/SKILL.md rule 2).",
            file=sys.stderr,
        )
    duration = parse_duration(args.duration)
    out = _safe_out_path(args.out) if args.out else (CAMCLAVE_DIR / "latest.png")
    cfg = {"token": s.token, "every": every, "until": time.time() + duration, "out_path": str(out)}
    safe_write_json(SNAPSHOT_CONFIG, cfg)
    print(f"camclave: snapshot mode on — every {every}s for {duration}s, writing {out}")


def cmd_snapshots_stop(_args: argparse.Namespace) -> None:
    s = active_session()
    if not s:
        print("camclave: no active session.")
        return
    if SNAPSHOT_CONFIG.exists():
        safe_write_json(SNAPSHOT_CONFIG, {"token": s.token, "disabled": True})
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
    safe_write_json(ADJUST_REQUEST, request)
    deadline = time.time() + 3
    while time.time() < deadline:
        resp = safe_read_json(ADJUST_RESPONSE)
        if resp is not None:
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
        resp = _send_adjust({"token": s.token, "show": True})
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

    resp = _send_adjust({"token": s.token, "set": settings})
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


def _device_names() -> dict[int, str]:
    """Best-effort map of OpenCV device index -> human-readable camera name.

    Windows: uses pygrabber (DSHOW filter graph). DSHOW enumeration order
    usually matches MSMF order, but it's not guaranteed — call it a hint.
    Linux:   reads /sys/class/video4linux/videoN/name (direct mapping).
    macOS:   no lookup yet; returns an empty dict.
    """
    if os.name == "nt":
        try:
            from pygrabber.dshow_graph import FilterGraph  # type: ignore

            return {i: n for i, n in enumerate(FilterGraph().get_input_devices())}
        except Exception:
            return {}
    if sys.platform.startswith("linux"):
        try:
            base = Path("/sys/class/video4linux")
            if not base.exists():
                return {}
            names: dict[int, str] = {}
            for p in sorted(base.glob("video*")):
                try:
                    idx = int(p.name[len("video"):])
                    names[idx] = (p / "name").read_text().strip()
                except Exception:
                    continue
            return names
        except Exception:
            return {}
    return {}


def cmd_doctor(_args: argparse.Namespace) -> None:
    """One-screen install / runtime / integrity diagnostic.

    Exits 0 if all REQUIRED checks pass; 1 if any required check failed.
    Optional checks (pygrabber, etc.) are reported but don't fail the run.
    """
    ok_all = True

    def line(status: str, label: str, detail: str = "") -> None:
        # status: "OK" | "WARN" | "FAIL". ASCII-only so cp1252 consoles don't
        # crash with UnicodeEncodeError.
        marker = {"OK": "OK ", "WARN": "-- ", "FAIL": "!! "}[status]
        end = "" if not detail else f"  -- {detail}"
        print(f"  [{marker}] {label}{end}")

    print("camclave doctor")
    print(f"  v{_read_pyproject_version()}  on  {sys.platform}\n")

    # 1. Python
    print("python runtime")
    line("OK", f"python {sys.version.split()[0]}", sys.executable)

    # 2. Required deps
    print("\ndependencies")
    for pkg in ("cv2", "PIL"):
        try:
            __import__(pkg)
            line("OK", pkg)
        except Exception as e:
            line("FAIL", pkg, f"import failed: {e}")
            ok_all = False
    try:
        import pygrabber  # type: ignore  # noqa
        line("OK", "pygrabber (optional, for device names)")
    except Exception:
        line("WARN", "pygrabber missing — device names won't show on Windows. Fix: pip install --user pygrabber")

    # 3. Skill symlinks
    print("\nskill discovery")
    for label, path in [
        ("Claude Code", Path.home() / ".claude" / "skills" / "camclave" / "SKILL.md"),
        ("Codex CLI",   Path.home() / ".codex"  / "skills" / "camclave" / "SKILL.md"),
    ]:
        if path.exists():
            line("OK", f"{label} skill installed", str(path))
        else:
            line("FAIL", f"{label} skill missing", f"expected {path}. Fix: re-run install.ps1 / install.sh")
            ok_all = False

    # 4. Shim on PATH (best-effort — only check expected location)
    print("\nshim")
    if os.name == "nt":
        shim = Path.home() / ".camclave" / "bin" / "camclave.cmd"
    else:
        shim = Path.home() / ".local" / "bin" / "camclave"
    if shim.exists():
        line("OK", "shim present", str(shim))
    else:
        line("WARN", "shim missing", f"expected {shim}. Fix: re-run installer.")

    # 5. ~/.camclave writable
    print("\nstorage")
    try:
        CAMCLAVE_DIR.mkdir(parents=True, exist_ok=True)
        test = CAMCLAVE_DIR / ".doctor-write-test"
        test.write_text("ok")
        test.unlink()
        line("OK", f"{CAMCLAVE_DIR} is writable")
    except Exception as e:
        line("FAIL", "~/.camclave not writable", str(e))
        ok_all = False

    # 6. Cameras
    print("\ncameras")
    names = _device_names()
    found_any = False
    try:
        import cv2
        backends = [("MSMF", cv2.CAP_MSMF), ("DSHOW", cv2.CAP_DSHOW)] if os.name == "nt" else [("ANY", cv2.CAP_ANY)]
        for i in range(4):
            for bname, b in backends:
                cap = cv2.VideoCapture(i, b)
                opens = cap.isOpened()
                ok_read = False
                if opens:
                    ok_read, _ = cap.read()
                cap.release()
                if ok_read:
                    nm = f" ({names[i]})" if i in names else ""
                    line("OK", f"device {i}: live via {bname}{nm}")
                    found_any = True
                    break
    except Exception as e:
        line("WARN", "camera probe error", str(e))
    if not found_any:
        line("WARN", "no working cameras found at indices 0..3")

    # 7. Session state
    print("\nsession")
    s = active_session()
    if s:
        line("OK", "active session", f"device {s.device}, {s.remaining_seconds}s remaining")
    else:
        line("OK", "no active session (this is fine — `camclave start` to begin)")

    # 8. Daemon log tail
    print("\ndaemon log")
    if DAEMON_LOG.exists() and DAEMON_LOG.stat().st_size > 0:
        try:
            lines = DAEMON_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
            if lines:
                print(f"  ~/.camclave/daemon.log (last {min(len(lines), 10)} lines):")
                for L in lines[-10:]:
                    print(f"    {L}")
        except Exception:
            line("WARN", "couldn't read daemon.log")
    else:
        line("OK", "daemon.log empty / absent (good — no recent launch error)")

    # 9. Integrity: confirm the safety claims on THIS installed copy.
    # We look for actual usage (imports or call sites), not bare keywords —
    # bare-keyword scans hit this very function's own search strings.
    print("\nintegrity audit (on installed code)")
    here = Path(__file__).resolve().parent
    # Patterns built piece-by-piece so the search strings don't appear as
    # literal substrings in this file (which would trigger self-matches).
    cv2_writer = "cv2" + r"\." + "VideoWriter" + r"\s*\("
    forbidden_patterns = [
        (re.compile(cv2_writer), "video-recording call site"),
        (re.compile(r"^\s*(import urllib|from urllib)", re.MULTILINE), "urllib (network)"),
        (re.compile(r"^\s*(import requests|from requests)", re.MULTILINE), "requests (network)"),
        (re.compile(r"^\s*(import socket|from socket)", re.MULTILINE), "socket (network)"),
        (re.compile(r"^\s*(import http|from http)", re.MULTILINE), "http (network)"),
    ]
    py_files = list(here.glob("*.py"))
    bad: list[tuple[str, str]] = []
    for py in py_files:
        try:
            content = py.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for pattern, label in forbidden_patterns:
            if pattern.search(content):
                bad.append((py.name, label))
    if bad:
        for f, n in bad:
            line("FAIL", f"{f}: {n}")
        ok_all = False
    else:
        line("OK", f"no video-writer or network imports across {len(py_files)} .py files")

    print("")
    if ok_all:
        print("camclave doctor: all required checks passed.")
    else:
        print("camclave doctor: one or more REQUIRED checks failed (see above).", file=sys.stderr)
        sys.exit(1)


def _read_pyproject_version() -> str:
    try:
        py = Path(__file__).resolve().parent.parent.parent / "pyproject.toml"
        for L in py.read_text().splitlines():
            if L.startswith("version"):
                return L.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return "?"


def cmd_devices(args: argparse.Namespace) -> None:
    import cv2

    if active_session() and args.preview:
        print(
            "camclave: a session is active — probing will skip the device it's using. "
            "(Other indices will still be previewed.)",
            file=sys.stderr,
        )

    names = _device_names()
    if names:
        if os.name == "nt":
            print("camclave: device names (DSHOW order; usually matches the indices below)")
        else:
            print("camclave: device names from /sys/class/video4linux")
        for idx, name in names.items():
            print(f"  [{idx}] {name}")
        print("")
    elif os.name == "nt":
        print(
            "camclave: device names unavailable (install `pygrabber` for them: "
            "`python -m pip install --user pygrabber`)"
        )
        print("")

    print("camclave: probing camera indices 0..5 (may briefly flash other cameras)")
    if os.name == "nt":
        backends = [("MSMF", cv2.CAP_MSMF), ("DSHOW", cv2.CAP_DSHOW)]
    else:
        backends = [("ANY", cv2.CAP_ANY)]

    previewed: list[tuple[int, str]] = []
    if args.preview:
        CAMCLAVE_DIR.mkdir(parents=True, exist_ok=True)

    for i in range(6):
        result = "—"
        frame_for_preview = None
        for name, backend in backends:
            cap = cv2.VideoCapture(i, backend)
            opens = cap.isOpened()
            ok = False
            if opens:
                ok, frame = cap.read()
                if ok and args.preview and frame is not None and frame_for_preview is None:
                    frame_for_preview = frame
            cap.release()
            if ok:
                result = f"live via {name}"
                break
            if opens and result == "—":
                result = f"opens but no frame ({name})"

        name_suffix = f"  ({names[i]})" if i in names else ""
        if args.preview and frame_for_preview is not None:
            out = CAMCLAVE_DIR / f"device-{i}.png"
            try:
                cv2.imwrite(str(out), frame_for_preview)
                previewed.append((i, str(out)))
                print(f"  device {i}: {result}{name_suffix}  ->  {out}")
            except Exception as e:
                print(f"  device {i}: {result}{name_suffix}  (preview write failed: {e})")
        else:
            print(f"  device {i}: {result}{name_suffix}")

    if args.preview:
        if previewed:
            print("")
            print(
                f"camclave: wrote {len(previewed)} thumbnail(s). "
                f"Open them to match index -> physical camera, then run "
                f"`camclave start --device <N>`."
            )
            print("(these files persist until next `devices --preview` overwrites them, "
                  "or you delete them manually)")
        else:
            print("\ncamclave: no working cameras found.")


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
    p.add_argument(
        "--reason",
        default="",
        help='short human-readable reason for this capture (shown in the preview window and recorded to ~/.camclave/audit.jsonl). Agents SHOULD pass this — see skill/SKILL.md.',
    )
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
    p.add_argument(
        "--preview",
        action="store_true",
        help="also save one PNG per working camera to ~/.camclave/device-<N>.png so you can visually identify which is which",
    )
    p.set_defaults(func=cmd_devices)

    p = sub.add_parser(
        "doctor",
        help="one-screen diagnostic: python/deps/skill/cameras/session/integrity",
    )
    p.set_defaults(func=cmd_doctor)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
