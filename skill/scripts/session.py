"""Session token + IPC paths for camclave.

The session.json on disk is the consent token. It's created by the preview
daemon when the user runs `camclave start` and is checked on every capture.
If the daemon process is dead or the TTL has expired, capture refuses.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path

CAMCLAVE_DIR = Path.home() / ".camclave"
SESSION_FILE = CAMCLAVE_DIR / "session.json"
CAPTURES_DIR = CAMCLAVE_DIR / "captures"
LATEST_FRAME = CAMCLAVE_DIR / "latest.jpg"
CAPTURE_REQUEST = CAMCLAVE_DIR / ".capture-request"
CAPTURE_RESPONSE = CAMCLAVE_DIR / ".capture-response"
SNAPSHOT_CONFIG = CAMCLAVE_DIR / "snapshot-config.json"

MAX_TTL_SECONDS = 60 * 60


@dataclass
class Session:
    pid: int
    device: int
    started_at: float
    ttl_seconds: int
    keep: bool
    no_sound: bool

    @property
    def expires_at(self) -> float:
        return self.started_at + self.ttl_seconds

    @property
    def expired(self) -> bool:
        return time.time() > self.expires_at

    @property
    def remaining_seconds(self) -> int:
        return max(0, int(self.expires_at - time.time()))


def ensure_dirs() -> None:
    CAMCLAVE_DIR.mkdir(parents=True, exist_ok=True)
    CAPTURES_DIR.mkdir(parents=True, exist_ok=True)


def write_session(s: Session) -> None:
    ensure_dirs()
    SESSION_FILE.write_text(json.dumps(asdict(s), indent=2))


def read_session() -> Session | None:
    if not SESSION_FILE.exists():
        return None
    try:
        return Session(**json.loads(SESSION_FILE.read_text()))
    except Exception:
        return None


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        kernel32 = ctypes.windll.kernel32
        h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not h:
            return False
        exit_code = ctypes.c_ulong(0)
        kernel32.GetExitCodeProcess(h, ctypes.byref(exit_code))
        kernel32.CloseHandle(h)
        return exit_code.value == STILL_ACTIVE
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def active_session() -> Session | None:
    s = read_session()
    if not s:
        return None
    if not pid_alive(s.pid):
        return None
    if s.expired:
        return None
    return s


def clear_session() -> None:
    for f in (SESSION_FILE, CAPTURE_REQUEST, CAPTURE_RESPONSE, SNAPSHOT_CONFIG, LATEST_FRAME):
        try:
            f.unlink()
        except FileNotFoundError:
            pass
