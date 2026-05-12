"""Tests for skill/scripts/camclave.py CLI helpers."""
import os
from pathlib import Path

import pytest

import camclave  # noqa: E402


# --- parse_duration ------------------------------------------------------

def test_parse_duration_bare_digits_is_seconds():
    assert camclave.parse_duration("30") == 30


def test_parse_duration_seconds_suffix():
    assert camclave.parse_duration("5s") == 5


def test_parse_duration_minutes_suffix():
    assert camclave.parse_duration("5m") == 300


def test_parse_duration_hours_suffix():
    assert camclave.parse_duration("1h") == 3600


def test_parse_duration_combined_units():
    assert camclave.parse_duration("1h30m") == 5400
    assert camclave.parse_duration("2h15m30s") == 8130


def test_parse_duration_case_insensitive():
    assert camclave.parse_duration("5M") == 300
    assert camclave.parse_duration("1H30M") == 5400


def test_parse_duration_unparseable_exits():
    with pytest.raises(SystemExit):
        camclave.parse_duration("xyz")
    with pytest.raises(SystemExit):
        camclave.parse_duration("")


# --- _safe_out_path ------------------------------------------------------

def test_safe_out_path_rejects_dotdot_segments():
    with pytest.raises(SystemExit) as ei:
        camclave._safe_out_path("../../foo.png")
    assert "--out rejected" in str(ei.value)


def test_safe_out_path_rejects_dotdot_in_middle():
    with pytest.raises(SystemExit):
        camclave._safe_out_path("/some/path/../../etc/passwd")


def test_safe_out_path_accepts_normal_absolute_path(tmp_path):
    target = tmp_path / "foo.png"
    out = camclave._safe_out_path(str(target))
    assert isinstance(out, Path)
    assert out.is_absolute()


def test_safe_out_path_expands_user(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    out = camclave._safe_out_path("~/foo.png")
    assert out.is_absolute()
    # Resolves to inside tmp_path (or its real-form, on macOS where /tmp is /private/tmp)
    assert "foo.png" in str(out)


SYMLINK_REASON = "symlink creation typically needs admin/dev-mode on Windows"


@pytest.mark.skipif(os.name == "nt", reason=SYMLINK_REASON)
def test_safe_out_path_rejects_symlinked_parent(tmp_path):
    real_dir = tmp_path / "real"
    real_dir.mkdir()
    linked_dir = tmp_path / "linked"
    linked_dir.symlink_to(real_dir)
    with pytest.raises(SystemExit) as ei:
        camclave._safe_out_path(str(linked_dir / "foo.png"))
    assert "symlink" in str(ei.value)
