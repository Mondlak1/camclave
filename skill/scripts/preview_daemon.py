"""Preview daemon: owns the camera, runs the always-on-top window,
honors capture and snapshot requests from the CLI.

This is a long-running process. The CLI's `camclave start` spawns it
detached, then exits. The session ends when (a) the user closes the
window, (b) the TTL expires, or (c) `camclave stop` kills the pid.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Quieter OpenCV — set before `import cv2` so it's picked up at init time.
os.environ.setdefault("OPENCV_LOG_LEVEL", "ERROR")

import cv2
import numpy as np
import tkinter as tk
from tkinter import font as tkfont
from PIL import Image, ImageTk

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from session import (  # noqa: E402
    ADJUST_REQUEST,
    ADJUST_RESPONSE,
    AUDIT_LOG,
    CAPTURE_REQUEST,
    CAPTURE_RESPONSE,
    CAPTURES_DIR,
    CAMCLAVE_DIR,
    MAX_TTL_SECONDS,
    SNAPSHOT_CONFIG,
    Session,
    clear_session,
    ensure_dirs,
    new_token,
    safe_read_json,
    safe_write_json,
    validate_payload,
    write_session,
)


def _check_token(req: dict, expected: str) -> bool:
    """Reject IPC requests without a matching session token.

    Returns True if the token is present and matches; False otherwise.
    Mismatches are silently rejected — we do not respond, do not log,
    do not flash. A foreign process that lacks the token cannot tell
    whether the daemon is running or not.
    """
    tok = req.get("token")
    return isinstance(tok, str) and tok == expected

PREVIEW_W = 520

# Palette — kept deliberately warm-but-serious. The red is unambiguous (this
# IS a safety indicator), but it's a deep crimson rather than neon, set off
# against a near-black warm interior and cream type. The pinkish dot breathes
# slowly to signal "active" without flickering.
PALETTE = {
    "border": "#b11226",      # outer crimson — safety signal
    "border_inner": "#7a0c1a", # thin bevel
    "panel": "#1c1418",        # warm near-black interior
    "panel_alt": "#251a1f",    # slightly raised band for footer
    "ink": "#f5e8e3",          # primary cream text
    "ink_dim": "#c4b9b3",      # muted warm-grey text
    "accent": "#d4a574",       # warm gold/rose — wordmark, TTL
    "dot_lo": "#ff6b6b",
    "dot_hi": "#ffd1d1",
}

# Adjustable camera properties exposed to `camclave adjust`. Maps the friendly
# name (used on the CLI and over IPC) to the OpenCV property constant.
# Some properties are toggles (auto-*); pass 0/1 for those. On Windows DSHOW,
# auto-exposure uses 0.25 = manual, 0.75 = auto — we pass values through as-is.
ADJUST_PROPS: dict[str, int] = {
    "brightness": cv2.CAP_PROP_BRIGHTNESS,
    "contrast": cv2.CAP_PROP_CONTRAST,
    "saturation": cv2.CAP_PROP_SATURATION,
    "hue": cv2.CAP_PROP_HUE,
    "gain": cv2.CAP_PROP_GAIN,
    "exposure": cv2.CAP_PROP_EXPOSURE,
    "focus": cv2.CAP_PROP_FOCUS,
    "zoom": cv2.CAP_PROP_ZOOM,
    "sharpness": cv2.CAP_PROP_SHARPNESS,
    "gamma": cv2.CAP_PROP_GAMMA,
    "auto_exposure": cv2.CAP_PROP_AUTO_EXPOSURE,
    "auto_focus": cv2.CAP_PROP_AUTOFOCUS,
    "auto_wb": cv2.CAP_PROP_AUTO_WB,
    "wb_temperature": cv2.CAP_PROP_WB_TEMPERATURE,
}


def open_camera(device: int) -> cv2.VideoCapture:
    """Open a camera, trying the best Windows backends in order.

    DirectShow (CAP_DSHOW) frequently can't enumerate physical webcams by
    index on Windows 10/11 even though it "is generally available", so we
    try Media Foundation (CAP_MSMF) first, then DSHOW, then leave the
    choice to OpenCV. On non-Windows we just use the default backend.
    """
    backends: list[tuple[str, int]]
    if os.name == "nt":
        backends = [("MSMF", cv2.CAP_MSMF), ("DSHOW", cv2.CAP_DSHOW), ("ANY", cv2.CAP_ANY)]
    else:
        backends = [("ANY", cv2.CAP_ANY)]
    errors: list[str] = []
    for name, backend in backends:
        cap = cv2.VideoCapture(device, backend)
        if not cap.isOpened():
            errors.append(f"{name}: cap.isOpened()=False")
            cap.release()
            continue
        ok, _ = cap.read()
        if not ok:
            errors.append(f"{name}: opened but cap.read() returned no frame")
            cap.release()
            continue
        # Don't force resolution post-open: changing format mid-stream destabilises
        # MSMF and triggers matrix-stride assertions on subsequent reads.
        return cap
    raise RuntimeError(
        f"Could not open camera device {device}. Tried: " + "; ".join(errors)
    )


def beep(suppress: bool) -> None:
    if suppress:
        return
    try:
        if os.name == "nt":
            import winsound

            winsound.Beep(880, 80)
        else:
            sys.stdout.write("\a")
            sys.stdout.flush()
    except Exception:
        pass


def _sweep_captures_dir() -> None:
    """Delete any stale frames left behind from a previous unclean shutdown.

    Run at startup so a crashed daemon's frames don't accumulate. Only touches
    files inside ~/.camclave/captures/ and the default snapshot at
    ~/.camclave/latest.png — never anything outside CAMCLAVE_DIR.
    """
    try:
        for p in CAPTURES_DIR.glob("*"):
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


def run(device: int, ttl: int, no_sound: bool, keep: bool) -> None:
    ensure_dirs()
    if not keep:
        _sweep_captures_dir()
    # Open the camera BEFORE writing session.json. If we wrote session.json
    # first and open_camera() then raised, cmd_start's poll loop could see
    # the briefly-existing session.json and the briefly-alive daemon pid and
    # declare victory before the daemon died — telling the user "preview
    # started" when in fact no camera ever opened. Reverse the order so
    # session.json only exists once we know the camera actually works.
    cap = open_camera(device)

    session = Session(
        pid=os.getpid(),
        token=new_token(),
        device=device,
        started_at=time.time(),
        ttl_seconds=ttl,
        keep=keep,
        no_sound=no_sound,
    )
    write_session(session)

    root = tk.Tk()
    root.title("camclave  •  CAMERA ACTIVE")
    root.attributes("-topmost", True)
    root.configure(bg=PALETTE["border"])

    state = {
        "flash_until": 0.0,
        "captures": 0,
        "shutting_down": False,
        "last_reason": "",
        "last_reason_until": 0.0,
    }
    snapshot_out_paths: set[Path] = set()  # tracks every snapshot --out path used

    def shutdown() -> None:
        if state["shutting_down"]:
            return
        state["shutting_down"] = True
        try:
            cap.release()
        except Exception:
            pass
        clear_session()
        if not keep:
            # Delete everything we wrote into ~/.camclave/captures/ this session
            for p in CAPTURES_DIR.glob("*"):
                if p.is_file():
                    try:
                        p.unlink()
                    except Exception:
                        pass
            # Also delete any snapshot --out file IF it lives inside ~/.camclave/.
            # Files the user explicitly pointed elsewhere (e.g. /tmp/print.png)
            # are left alone — they asked for them there.
            try:
                camclave_root = CAMCLAVE_DIR.resolve()
            except Exception:
                camclave_root = CAMCLAVE_DIR
            for p in snapshot_out_paths:
                try:
                    resolved = p.resolve()
                except Exception:
                    continue
                try:
                    resolved.relative_to(camclave_root)
                except ValueError:
                    continue  # outside our dir; leave it
                if resolved.exists() and resolved.is_file():
                    try:
                        resolved.unlink()
                    except Exception:
                        pass
        try:
            root.destroy()
        except Exception:
            pass

    root.protocol("WM_DELETE_WINDOW", shutdown)

    # Fonts — prefer Segoe UI on Windows, Cascadia Mono / Consolas for the
    # TTL clock so its digits don't jiggle as time decreases. Falls back
    # gracefully if a font is missing.
    available_fonts = set(tkfont.families())
    body_family = "Segoe UI" if "Segoe UI" in available_fonts else "Helvetica"
    mono_family = next(
        (f for f in ("Cascadia Mono", "Consolas", "Menlo", "DejaVu Sans Mono") if f in available_fonts),
        "Courier",
    )
    f_header = tkfont.Font(family=body_family, size=11, weight="bold")
    f_wordmark = tkfont.Font(family=body_family, size=10, weight="normal", slant="italic")
    f_mode = tkfont.Font(family=body_family, size=9, weight="bold")
    f_ttl = tkfont.Font(family=mono_family, size=10, weight="normal")

    # Visible safety border. The outermost frame IS the red ring; everything
    # else lives in a warm-dark inner panel.
    border_outer = 5     # thick crimson ring
    border_inset = 1     # thin darker bevel inside the ring for depth
    pad_x = 14
    pad_y_top = 12
    pad_y_mid = 10
    pad_y_bot = 12

    outer = tk.Frame(root, bg=PALETTE["border"])
    outer.pack(padx=0, pady=0)

    bevel = tk.Frame(outer, bg=PALETTE["border_inner"])
    bevel.pack(padx=border_outer, pady=border_outer)

    panel = tk.Frame(bevel, bg=PALETTE["panel"])
    panel.pack(padx=border_inset, pady=border_inset)

    # Header row: breathing dot + CAMERA ACTIVE + right-aligned wordmark
    header = tk.Frame(panel, bg=PALETTE["panel"])
    header.pack(fill="x", padx=pad_x, pady=(pad_y_top, pad_y_mid))

    dot_canvas = tk.Canvas(
        header, width=14, height=14, bg=PALETTE["panel"], highlightthickness=0, bd=0
    )
    dot_canvas.pack(side="left", padx=(0, 8))
    dot_oval = dot_canvas.create_oval(2, 2, 12, 12, fill=PALETTE["dot_lo"], outline="")

    title = tk.Label(
        header,
        text="CAMERA ACTIVE",
        bg=PALETTE["panel"],
        fg=PALETTE["ink"],
        font=f_header,
        anchor="w",
    )
    title.pack(side="left")

    wordmark = tk.Label(
        header,
        text="camclave",
        bg=PALETTE["panel"],
        fg=PALETTE["accent"],
        font=f_wordmark,
        anchor="e",
    )
    wordmark.pack(side="right")

    # Image
    img_label = tk.Label(panel, bg=PALETTE["panel"], bd=0, highlightthickness=0)
    img_label.pack(padx=pad_x, pady=0)

    # Footer row: live mode (left) + ttl (right)
    footer = tk.Frame(panel, bg=PALETTE["panel_alt"])
    footer.pack(fill="x", padx=pad_x, pady=(pad_y_mid, pad_y_bot))

    mode_label = tk.Label(
        footer,
        text="● live",
        bg=PALETTE["panel_alt"],
        fg=PALETTE["ink_dim"],
        font=f_mode,
        anchor="w",
        padx=10,
        pady=6,
    )
    mode_label.pack(side="left")

    ttl_label = tk.Label(
        footer,
        text="00:00",
        bg=PALETTE["panel_alt"],
        fg=PALETTE["ink"],
        font=f_ttl,
        anchor="e",
        padx=10,
        pady=6,
    )
    ttl_label.pack(side="right")

    def lerp_color(c1: str, c2: str, t: float) -> str:
        t = max(0.0, min(1.0, t))
        r1, g1, b1 = int(c1[1:3], 16), int(c1[3:5], 16), int(c1[5:7], 16)
        r2, g2, b2 = int(c2[1:3], 16), int(c2[3:5], 16), int(c2[5:7], 16)
        r = int(r1 + (r2 - r1) * t)
        g = int(g1 + (g2 - g1) * t)
        b = int(b1 + (b2 - b1) * t)
        return f"#{r:02x}{g:02x}{b:02x}"

    snapshot_state = {"next_at": 0.0, "until": 0.0, "every": 0.0, "out_path": ""}

    def _consume_request(path) -> dict | None:
        """Read + validate + authenticate an IPC request file.

        Returns the parsed dict if it's authentic (token matches), otherwise
        deletes the file and returns None. Symlinks / malformed JSON / wrong
        token all yield None. No response is written for rejected requests
        — silence is the right answer for unauthenticated callers.
        """
        if not path.exists():
            return None
        req = safe_read_json(path)
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        if req is None:
            return None
        if not _check_token(req, session.token):
            return None
        return req

    def handle_adjust_request() -> None:
        """Apply property changes the CLI requested, write back what stuck.

        Most webcams silently clip out-of-range values; we report what
        cap.get() returns AFTER the set so the CLI can show the user what
        actually took effect.
        """
        req = _consume_request(ADJUST_REQUEST)
        if req is None:
            return
        applied: dict[str, float] = {}
        rejected: list[str] = []
        if bool(req.get("show")):
            for name, prop in ADJUST_PROPS.items():
                applied[name] = float(cap.get(prop))
        else:
            settings = req.get("set", {})
            if not isinstance(settings, dict):
                settings = {}
            for name, value in settings.items():
                prop = ADJUST_PROPS.get(name)
                if prop is None:
                    rejected.append(name)
                    continue
                try:
                    cap.set(prop, float(value))
                    applied[name] = float(cap.get(prop))
                except Exception:
                    rejected.append(name)
        try:
            safe_write_json(
                ADJUST_RESPONSE,
                {"applied": applied, "rejected": rejected, "ts": time.time()},
            )
        except Exception:
            pass

    def handle_capture_request(frame_bgr) -> None:
        req = _consume_request(CAPTURE_REQUEST)
        if req is None:
            return
        out_path = req.get("out_path")
        if not isinstance(out_path, str) or not out_path:
            ts = datetime.now().strftime("%Y%m%dT%H%M%S%f")[:-3]
            out_path = str(CAPTURES_DIR / f"frame-{ts}.png")
        reason = req.get("reason") if isinstance(req.get("reason"), str) else None

        try:
            Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            try:
                safe_write_json(CAPTURE_RESPONSE, {"error": f"could not create parent dir: {e}"})
            except Exception:
                pass
            return

        # imwrite returns False on disk full, permission denied, bad ext,
        # invalid path, etc. Surface that to the CLI instead of fake success.
        try:
            ok = cv2.imwrite(out_path, frame_bgr)
        except Exception as e:
            ok = False
            err = str(e)
        else:
            err = "cv2.imwrite returned False (disk full, permission, or invalid path)"
        if not ok:
            try:
                safe_write_json(CAPTURE_RESPONSE, {"error": err})
            except Exception:
                pass
            return

        state["captures"] += 1
        state["flash_until"] = time.time() + 0.35
        if reason:
            state["last_reason"] = reason
            state["last_reason_until"] = time.time() + 4.0
        beep(no_sound)

        # Audit trail — one JSONL line per capture (in addition to the
        # always-visible flash + beep + window mode indicator).
        try:
            with AUDIT_LOG.open("a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "ts": time.time(),
                    "kind": "capture",
                    "path": out_path,
                    "reason": reason,
                    "captures_so_far": state["captures"],
                }) + "\n")
        except Exception:
            pass

        try:
            safe_write_json(
                CAPTURE_RESPONSE,
                {"path": out_path, "ts": time.time(), "reason": reason},
            )
        except Exception:
            pass

    def reload_snapshot_config() -> None:
        cfg = safe_read_json(SNAPSHOT_CONFIG)
        if not cfg:
            snapshot_state["until"] = 0
            return
        # Token authentication — drop unauthenticated config silently.
        if not _check_token(cfg, session.token):
            try:
                SNAPSHOT_CONFIG.unlink()
            except FileNotFoundError:
                pass
            return
        if cfg.get("disabled"):
            snapshot_state["until"] = 0
            try:
                SNAPSHOT_CONFIG.unlink()
            except FileNotFoundError:
                pass
            return
        try:
            every = float(cfg.get("every", 0))
            until = float(cfg.get("until", 0))
        except (TypeError, ValueError):
            return
        out_raw = cfg.get("out_path")
        out_path = out_raw if isinstance(out_raw, str) and out_raw else str(CAMCLAVE_DIR / "latest.png")
        if every != snapshot_state["every"] or until != snapshot_state["until"]:
            snapshot_state["every"] = every
            snapshot_state["until"] = until
            snapshot_state["out_path"] = out_path
            snapshot_state["next_at"] = time.time()

    def handle_snapshot(frame_bgr) -> None:
        reload_snapshot_config()
        now = time.time()
        if snapshot_state["until"] and now >= snapshot_state["next_at"] and now < snapshot_state["until"]:
            out = Path(snapshot_state["out_path"])
            try:
                out.parent.mkdir(parents=True, exist_ok=True)
                ok = cv2.imwrite(str(out), frame_bgr)
            except Exception:
                ok = False
            if ok:
                snapshot_out_paths.add(out)
                snapshot_state["next_at"] = now + snapshot_state["every"]
                state["flash_until"] = max(state["flash_until"], now + 0.2)
                beep(no_sound)
                # Audit
                try:
                    with AUDIT_LOG.open("a", encoding="utf-8") as f:
                        f.write(json.dumps({
                            "ts": now,
                            "kind": "snapshot",
                            "path": str(out),
                            "every": snapshot_state["every"],
                        }) + "\n")
                except Exception:
                    pass
            else:
                # Skip this tick; back off slightly so we don't spin on a
                # broken output path.
                snapshot_state["next_at"] = now + max(snapshot_state["every"], 2.0)
        if snapshot_state["until"] and now >= snapshot_state["until"]:
            try:
                SNAPSHOT_CONFIG.unlink()
            except FileNotFoundError:
                pass
            snapshot_state["until"] = 0

    def loop() -> None:
        if state["shutting_down"]:
            return
        if time.time() > session.expires_at:
            shutdown()
            return
        ok, frame = cap.read()
        if not ok or frame is None:
            mode_label.config(text="● no signal", fg=PALETTE["dot_lo"])
            ttl_label.config(text="--:--")
            root.after(500, loop)
            return

        # No continuous frame storage. The daemon never writes a rolling jpg /
        # ring buffer to disk; frames only land on disk when capture or
        # snapshot mode explicitly asks for one. See references/safety.md.
        handle_adjust_request()
        handle_capture_request(frame)
        handle_snapshot(frame)

        now = time.time()

        # Soft capture flash: ease-out warm cream wash over ~350ms instead of
        # a hard white pop. Less startling, still unmistakable.
        flash_remaining = state["flash_until"] - now
        if flash_remaining > 0:
            alpha = min(0.80, (flash_remaining / 0.35) ** 1.5)  # ease-out
            overlay = np.full(frame.shape, (227, 232, 245), dtype=frame.dtype)  # BGR cream
            display = cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0)
        else:
            display = frame

        h, w = display.shape[:2]
        scale = PREVIEW_W / w
        display = cv2.resize(display, (PREVIEW_W, max(1, int(h * scale))), interpolation=cv2.INTER_AREA)
        rgb = cv2.cvtColor(display, cv2.COLOR_BGR2RGB)
        pil = Image.fromarray(rgb)
        tkimg = ImageTk.PhotoImage(pil)
        img_label.configure(image=tkimg)
        img_label.image = tkimg

        # Breathing dot: sinusoidal interpolation between dim and bright pink
        # over a ~1.6s period. Quiet visual signal that the camera is live.
        breath = 0.5 * (1 + math.sin(now * (2 * math.pi / 1.6)))
        dot_canvas.itemconfig(dot_oval, fill=lerp_color(PALETTE["dot_lo"], PALETTE["dot_hi"], breath))

        # Mode indicator: tells the user what camclave is doing right now
        # (the header above never changes — it's the safety signal).
        # If a recent capture had a --reason, show it for ~4s after the flash
        # — this is the visible audit trail that tells the user WHY the agent
        # just took a frame.
        reason_active = state.get("last_reason") and now < state.get("last_reason_until", 0)
        if reason_active:
            r = state["last_reason"]
            mode_text, mode_fg = f"● capturing — {r}", PALETTE["dot_lo"]
        elif flash_remaining > 0:
            mode_text, mode_fg = f"● capturing  ({state['captures']})", PALETTE["dot_lo"]
        elif snapshot_state["until"] and now < snapshot_state["until"]:
            every = int(snapshot_state["every"])
            mode_text, mode_fg = f"● snapshot mode  every {every}s  ({state['captures']})", PALETTE["accent"]
        else:
            mode_text, mode_fg = f"● live  ({state['captures']} captured)", PALETTE["ink_dim"]
        mode_label.config(text=mode_text, fg=mode_fg)

        remaining = max(0, int(session.expires_at - now))
        mm, ss = divmod(remaining, 60)
        ttl_label.config(text=f"ttl  {mm:02d}:{ss:02d}")

        root.after(50, loop)  # ~20 fps, smoother breathing

    loop()
    try:
        root.mainloop()
    finally:
        shutdown()


def _redirect_to_log() -> None:
    """Send daemon stdout+stderr to ~/.camclave/daemon.log.

    Done from inside the daemon (rather than parent-side Popen redirection)
    because Windows DETACHED_PROCESS doesn't play well with parent-supplied
    file handles. This way the daemon owns its own log and a startup
    exception lands somewhere the CLI can read on the next status check.
    """
    try:
        ensure_dirs()
        from session import DAEMON_LOG as _LOG
        f = open(str(_LOG), "w", encoding="utf-8", errors="replace")
        sys.stdout = f
        sys.stderr = f
    except Exception:
        pass


def main() -> None:
    _redirect_to_log()
    try:
        ap = argparse.ArgumentParser()
        ap.add_argument("--device", type=int, default=0)
        ap.add_argument("--ttl", type=int, default=900)
        ap.add_argument("--no-sound", action="store_true")
        ap.add_argument("--keep", action="store_true")
        args = ap.parse_args()
        ttl = min(max(args.ttl, 10), MAX_TTL_SECONDS)
        run(args.device, ttl, args.no_sound, args.keep)
    except SystemExit:
        raise
    except BaseException:
        import traceback
        traceback.print_exc()
        sys.stderr.flush()
        raise


if __name__ == "__main__":
    main()
