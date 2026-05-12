"""Tests for skill/scripts/session.py — pure helpers, no camera, no daemon."""
import json
import os
from pathlib import Path

import pytest

from session import (  # noqa: E402
    Session,
    TOKEN_BYTES,
    new_token,
    safe_read_json,
    safe_write_json,
    validate_payload,
)


# --- token ---------------------------------------------------------------

def test_new_token_is_32_hex_chars():
    t = new_token()
    assert len(t) == TOKEN_BYTES * 2 == 32
    assert all(c in "0123456789abcdef" for c in t)


def test_new_token_is_unpredictable():
    # Not a real entropy test — but two consecutive nonces should never match.
    seen = {new_token() for _ in range(20)}
    assert len(seen) == 20


# --- Session dataclass ---------------------------------------------------

def test_session_expires_at_is_started_plus_ttl():
    s = Session(pid=1, token="a" * 32, device=0, started_at=100.0,
                ttl_seconds=30, keep=False, no_sound=False)
    assert s.expires_at == 130.0


def test_session_expired_when_past_ttl():
    # started_at = 0 means expires at TTL seconds after epoch — definitely expired now.
    s = Session(pid=1, token="a" * 32, device=0, started_at=0.0,
                ttl_seconds=10, keep=False, no_sound=False)
    assert s.expired is True
    assert s.remaining_seconds == 0


# --- validate_payload ----------------------------------------------------

def test_validate_payload_happy_path():
    assert validate_payload({"a": 1, "b": "x"}, {"a": int, "b": str}) is True


def test_validate_payload_extra_keys_allowed():
    assert validate_payload({"a": 1, "extra": "ignored"}, {"a": int}) is True


def test_validate_payload_missing_key_rejected():
    assert validate_payload({"a": 1}, {"a": int, "b": str}) is False


def test_validate_payload_wrong_type_rejected():
    assert validate_payload({"a": "not-an-int"}, {"a": int}) is False


def test_validate_payload_non_dict_rejected():
    assert validate_payload([1, 2, 3], {"a": int}) is False
    assert validate_payload(None, {"a": int}) is False
    assert validate_payload("string", {"a": int}) is False


def test_validate_payload_tuple_of_types():
    assert validate_payload({"a": 1.5}, {"a": (int, float)}) is True
    assert validate_payload({"a": 1}, {"a": (int, float)}) is True
    assert validate_payload({"a": "x"}, {"a": (int, float)}) is False


# --- safe_write_json / safe_read_json -----------------------------------

def test_safe_write_read_round_trip(tmp_path):
    f = tmp_path / "x.json"
    payload = {"hello": "world", "n": 42, "nested": {"k": [1, 2, 3]}}
    safe_write_json(f, payload)
    assert safe_read_json(f) == payload


def test_safe_read_returns_none_for_missing(tmp_path):
    assert safe_read_json(tmp_path / "nope.json") is None


def test_safe_read_returns_none_for_non_dict_json(tmp_path):
    f = tmp_path / "list.json"
    f.write_text(json.dumps([1, 2, 3]))
    assert safe_read_json(f) is None


def test_safe_read_returns_none_for_malformed_json(tmp_path):
    f = tmp_path / "bad.json"
    f.write_text("{not valid json")
    assert safe_read_json(f) is None


def test_safe_write_leaves_no_tmp_file_on_success(tmp_path):
    f = tmp_path / "x.json"
    safe_write_json(f, {"ok": True})
    assert not (tmp_path / "x.json.tmp").exists()


def test_safe_write_overwrites_existing(tmp_path):
    f = tmp_path / "x.json"
    safe_write_json(f, {"v": 1})
    safe_write_json(f, {"v": 2})
    assert safe_read_json(f) == {"v": 2}


# Symlink defenses — symlink creation requires admin/dev-mode on Windows
# (and the GHA Windows runners default off), so we skip there. The Linux
# matrix entry covers this behavior.
SYMLINK_REASON = "symlink creation typically needs admin/dev-mode on Windows"


@pytest.mark.skipif(os.name == "nt", reason=SYMLINK_REASON)
def test_safe_write_unlinks_target_symlink_first(tmp_path):
    """Critical: writing to an IPC path must NOT follow a preplaced symlink
    that points at some innocent file the attacker wants overwritten."""
    real_target = tmp_path / "do-not-touch.txt"
    real_target.write_text("untouched")

    fixed_path = tmp_path / "ipc.json"
    fixed_path.symlink_to(real_target)

    safe_write_json(fixed_path, {"new": True})

    # The unrelated target file must be unchanged.
    assert real_target.read_text() == "untouched"
    # The fixed_path is no longer a symlink — replaced with a regular file.
    assert not fixed_path.is_symlink()
    assert safe_read_json(fixed_path) == {"new": True}


@pytest.mark.skipif(os.name == "nt", reason=SYMLINK_REASON)
def test_safe_read_refuses_symlinked_path(tmp_path):
    """Even if the symlink targets a valid JSON file, we refuse to read it.
    This means an attacker can't get the daemon to "see" their crafted
    request by symlinking the IPC file to attacker-controlled content."""
    target = tmp_path / "target.json"
    target.write_text(json.dumps({"crafted": True}))

    link = tmp_path / "ipc.json"
    link.symlink_to(target)

    assert safe_read_json(link) is None
