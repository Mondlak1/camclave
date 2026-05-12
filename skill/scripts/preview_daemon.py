"""Preview daemon: owns the camera, runs the always-on-top window,
honors capture and snapshot requests from the CLI.

This is a long-running process. The CLI's `camclave start` spawns it
detached, then exits. The session ends when (a) the user closes the
window, (b) the TTL expires, or (c) `camclave stop` kills the pid.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import cv2
import tkinter as tk
from PIL import Image, ImageTk

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from session import (  # noqa: E402
    CAPTURE_REQUEST,
    CAPTURE_RESPONSE,
    CAPTURES_DIR,
    LATEST_FRAME,
    CAMCLAVE_DIR,
    MAX_TTL_SECONDS,
    SNAPSHOT_CONFIG,
    Session,
    clear_session,
    ensure_dirs,
    write_session,
)

PREVIEW_W = 480
RED = "#d11a1a"
RED_BRIGHT = "#ff2a2a"


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


def run(device: int, ttl: int, no_sound: bool, keep: bool) -> None:
    ensure_dirs()
    session = Session(
        pid=os.getpid(),
        device=device,
        started_at=time.time(),
        ttl_seconds=ttl,
        keep=keep,
        no_sound=no_sound,
    )
    write_session(session)

    cap = open_camera(device)

    root = tk.Tk()
    root.title("camclave — CAMERA ACTIVE")
    root.attributes("-topmost", True)
    root.configure(bg=RED)

    state = {"flash_until": 0.0, "captures": 0, "shutting_down": False}

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
            for p in CAPTURES_DIR.glob("frame-*.png"):
                try:
                    p.unlink()
                except Exception:
                    pass
        try:
            root.destroy()
        except Exception:
            pass

    root.protocol("WM_DELETE_WINDOW", shutdown)

    border = 6
    outer = tk.Frame(root, bg=RED)
    outer.pack()

    header = tk.Label(
        outer,
        text="● CAMERA ACTIVE — camclave",
        bg=RED,
        fg="white",
        font=("Segoe UI", 10, "bold"),
        anchor="w",
    )
    header.pack(fill="x", padx=border, pady=(border, 2))

    inner = tk.Frame(outer, bg=RED)
    inner.pack(padx=border, pady=(0, 2))
    img_label = tk.Label(inner, bg="black")
    img_label.pack()

    footer = tk.Label(
        outer,
        text="frames: 0   ttl: 00:00",
        bg=RED,
        fg="white",
        font=("Segoe UI", 9),
        anchor="w",
    )
    footer.pack(fill="x", padx=border, pady=(2, border))

    snapshot_state = {"next_at": 0.0, "until": 0.0, "every": 0.0, "out_path": ""}

    def handle_capture_request(frame_bgr) -> None:
        if not CAPTURE_REQUEST.exists():
            return
        try:
            text = CAPTURE_REQUEST.read_text()
        except FileNotFoundError:
            return
        try:
            req = json.loads(text) if text.strip().startswith("{") else {}
        except Exception:
            req = {}
        out_path = req.get("out_path")
        if not out_path:
            ts = datetime.now().strftime("%Y%m%dT%H%M%S%f")[:-3]
            out_path = str(CAPTURES_DIR / f"frame-{ts}.png")
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(out_path, frame_bgr)
        state["captures"] += 1
        state["flash_until"] = time.time() + 0.18
        beep(no_sound)
        try:
            CAPTURE_RESPONSE.write_text(json.dumps({"path": out_path, "ts": time.time()}))
        except Exception:
            pass
        try:
            CAPTURE_REQUEST.unlink()
        except FileNotFoundError:
            pass

    def reload_snapshot_config() -> None:
        if not SNAPSHOT_CONFIG.exists():
            snapshot_state["until"] = 0
            return
        try:
            cfg = json.loads(SNAPSHOT_CONFIG.read_text())
        except Exception:
            return
        if cfg.get("disabled"):
            snapshot_state["until"] = 0
            try:
                SNAPSHOT_CONFIG.unlink()
            except FileNotFoundError:
                pass
            return
        every = float(cfg.get("every", 0))
        until = float(cfg.get("until", 0))
        out_path = cfg.get("out_path") or str(CAMCLAVE_DIR / "latest.png")
        if every != snapshot_state["every"] or until != snapshot_state["until"]:
            snapshot_state["every"] = every
            snapshot_state["until"] = until
            snapshot_state["out_path"] = out_path
            snapshot_state["next_at"] = time.time()

    def handle_snapshot(frame_bgr) -> None:
        reload_snapshot_config()
        now = time.time()
        if snapshot_state["until"] and now >= snapshot_state["next_at"] and now < snapshot_state["until"]:
            Path(snapshot_state["out_path"]).parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(snapshot_state["out_path"], frame_bgr)
            snapshot_state["next_at"] = now + snapshot_state["every"]
            state["flash_until"] = max(state["flash_until"], now + 0.1)
            beep(no_sound)
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
            footer.config(text="  no frame from camera (in use by another app?)")
            root.after(500, loop)
            return

        try:
            cv2.imwrite(str(LATEST_FRAME), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
        except Exception:
            pass

        handle_capture_request(frame)
        handle_snapshot(frame)

        flashing = time.time() < state["flash_until"]
        if flashing:
            display = frame.copy()
            display[:] = 255
        else:
            display = frame

        h, w = display.shape[:2]
        scale = PREVIEW_W / w
        display = cv2.resize(display, (PREVIEW_W, max(1, int(h * scale))))
        rgb = cv2.cvtColor(display, cv2.COLOR_BGR2RGB)
        pil = Image.fromarray(rgb)
        tkimg = ImageTk.PhotoImage(pil)
        img_label.configure(image=tkimg)
        img_label.image = tkimg

        remaining = max(0, int(session.expires_at - time.time()))
        mm, ss = divmod(remaining, 60)
        footer.config(
            text=f"frames captured: {state['captures']}   ttl: {mm:02d}:{ss:02d}   device: {device}"
        )

        # subtle pulsing header so the user keeps noticing the window
        header.config(bg=RED_BRIGHT if int(time.time() * 2) % 2 else RED)

        root.after(66, loop)

    loop()
    try:
        root.mainloop()
    finally:
        shutdown()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", type=int, default=0)
    ap.add_argument("--ttl", type=int, default=900)
    ap.add_argument("--no-sound", action="store_true")
    ap.add_argument("--keep", action="store_true")
    args = ap.parse_args()
    ttl = min(max(args.ttl, 10), MAX_TTL_SECONDS)
    run(args.device, ttl, args.no_sound, args.keep)


if __name__ == "__main__":
    main()
