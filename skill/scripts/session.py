"""Session token + IPC paths + safe-IO helpers for camclave.

The session.json on disk is the consent token. It's created by the preview
daemon when the user runs `camclave start` and is checked on every capture.
If the daemon process is dead or the TTL has expired, capture refuses.

v0.5.0 hardening:
  - `Session.token` is a 32-char hex nonce generated at daemon start.
    Every IPC request must include the matching token; mismatches are
    rejected silently. This authenticates the caller against the
    daemon-owned session.json, which is written with mode 0o600.
  - `safe_write_json` / `safe_read_json` refuse to follow symlinks at
    the target path or its `.tmp` sibling, and use temp-then-rename for
    atomicity. Defends against symlink preplacement on fixed-name IPC
    files.
  - `validate_payload` does a one-pass type check against a tiny schema
    spec so malformed IPC is rejected deterministically instead of
    crashing or being half-applied.
"""
from __future__ import annotations

import json
import os
import secrets
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

CAMCLAVE_DIR = Path.home() / ".camclave"
SESSION_FILE = CAMCLAVE_DIR / "session.json"
CAPTURES_DIR = CAMCLAVE_DIR / "captures"
CAPTURE_REQUEST = CAMCLAVE_DIR / ".capture-request"
CAPTURE_RESPONSE = CAMCLAVE_DIR / ".capture-response"
SNAPSHOT_CONFIG = CAMCLAVE_DIR / "snapshot-config.json"
ADJUST_REQUEST = CAMCLAVE_DIR / ".adjust-request"
ADJUST_RESPONSE = CAMCLAVE_DIR / ".adjust-response"
DAEMON_LOG = CAMCLAVE_DIR / "daemon.log"
AUDIT_LOG = CAMCLAVE_DIR / "audit.jsonl"

MAX_TTL_SECONDS = 60 * 60
TOKEN_BYTES = 16  # -> 32 hex chars


@dataclass
class Session:
    pid: int
    token: str
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


def new_token() -> str:
    return secrets.token_hex(TOKEN_BYTES)


def ensure_dirs() -> None:
    CAMCLAVE_DIR.mkdir(parents=True, exist_ok=True)
    CAPTURES_DIR.mkdir(parents=True, exist_ok=True)


# --- safe IO helpers --------------------------------------------------------

def _unlink_if_symlink(path: Path) -> None:
    """If `path` is a symlink, remove it (do NOT follow). No-op otherwise."""
    try:
        if path.is_symlink():
            path.unlink()
    except FileNotFoundError:
        pass
    except OSError:
        pass


def safe_write_json(path: Path, payload: dict, mode: int = 0o600) -> None:
    """Atomic, no-symlink-follow JSON write to a fixed-name IPC file.

    1. If `path` or its `.tmp` sibling is currently a symlink, unlink it
       (instead of writing through to the target).
    2. Write payload to a temp file using a fresh file descriptor opened
       with O_CREAT|O_TRUNC|O_WRONLY (POSIX) so symlink targets aren't
       picked up. On Windows this maps to the same semantics via os.open.
    3. os.replace() to swap the temp file into place atomically.

    On any failure, the temp file is removed and the exception re-raised.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    _unlink_if_symlink(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    _unlink_if_symlink(tmp)

    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    # O_NOFOLLOW where available; defends if a symlink slipped in between
    # our is_symlink check and the open.
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    if os.name == "nt" and hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY

    try:
        fd = os.open(str(tmp), flags, mode)
    except OSError:
        # Fall back to plain open if O_NOFOLLOW wasn't supported by the FS
        flags &= ~getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(str(tmp), flags, mode)

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f)
    except BaseException:
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass
        raise
    os.replace(str(tmp), str(path))


def safe_read_json(path: Path) -> dict | None:
    """Read JSON refusing to follow symlinks. Returns None on any failure."""
    try:
        if path.is_symlink():
            return None
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


# --- schema validation ------------------------------------------------------

def validate_payload(d: Any, schema: dict[str, type | tuple[type, ...]]) -> bool:
    """Cheap type check against a {key: type} schema.

    Returns True only if `d` is a dict, contains every key in `schema`,
    and each value is an instance of the declared type(s). Extra keys
    are allowed.
    """
    if not isinstance(d, dict):
        return False
    for key, expected in schema.items():
        if key not in d:
            return False
        if not isinstance(d[key], expected):
            return False
    return True


# --- session lifecycle ------------------------------------------------------

def write_session(s: Session) -> None:
    ensure_dirs()
    safe_write_json(SESSION_FILE, asdict(s), mode=0o600)


def read_session() -> Session | None:
    data = safe_read_json(SESSION_FILE)
    if not data:
        return None
    # Backwards compat: tolerate sessions written by v<0.5.0 (no token).
    # Treat them as invalid so callers refuse to use them.
    if not validate_payload(
        data,
        {
            "pid": int,
            "device": int,
            "started_at": (int, float),
            "ttl_seconds": int,
            "keep": bool,
            "no_sound": bool,
        },
    ):
        return None
    if not isinstance(data.get("token"), str) or len(data.get("token", "")) != TOKEN_BYTES * 2:
        return None
    try:
        return Session(**data)
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
    for f in (
        SESSION_FILE,
        CAPTURE_REQUEST,
        CAPTURE_RESPONSE,
        SNAPSHOT_CONFIG,
        ADJUST_REQUEST,
        ADJUST_RESPONSE,
        AUDIT_LOG,
    ):
        try:
            f.unlink()
        except FileNotFoundError:
            pass
