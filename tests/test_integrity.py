"""Verifies camclave's safety claims AT THE SOURCE LEVEL.

The `camclave doctor` command runs an equivalent check at runtime; this
test runs the same patterns in CI so any PR that introduces a video
writer or network import fails before merge — not just at the user's
next `doctor` invocation.

Patterns are intentionally built piece-by-piece (string concatenation
rather than literal substrings) so they don't appear in this file and
self-match.
"""
import re
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "skill" / "scripts"


def _all_skill_py_files() -> list[Path]:
    files = [p for p in SCRIPTS_DIR.glob("*.py") if p.name != "__init__.py"]
    assert files, f"no .py files found under {SCRIPTS_DIR} — test setup broken"
    return files


def test_no_video_writer_call_site():
    pattern = re.compile("cv2" + r"\." + "VideoWriter" + r"\s*\(")
    bad = [p.name for p in _all_skill_py_files() if pattern.search(p.read_text(encoding="utf-8"))]
    assert not bad, f"video-recording call site found in: {bad}"


@pytest.mark.parametrize("label,regex", [
    ("urllib", r"^\s*(import urllib|from urllib)"),
    ("requests", r"^\s*(import requests|from requests)"),
    ("socket", r"^\s*(import socket|from socket)"),
    ("http", r"^\s*(import http|from http)"),
    ("httpx", r"^\s*(import httpx|from httpx)"),
    ("aiohttp", r"^\s*(import aiohttp|from aiohttp)"),
])
def test_no_network_imports(label, regex):
    pat = re.compile(regex, re.MULTILINE)
    bad = [p.name for p in _all_skill_py_files() if pat.search(p.read_text(encoding="utf-8"))]
    assert not bad, f"{label} import found in: {bad}"


def test_pyproject_version_is_a_semver():
    py = Path(__file__).resolve().parent.parent / "pyproject.toml"
    text = py.read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    assert m, "no version field found in pyproject.toml"
    version = m.group(1)
    # Permissive semver — accepts 0.6.0, 1.2.3-rc1, etc.
    assert re.match(r"^\d+\.\d+\.\d+(?:[-+].+)?$", version), f"bad version: {version}"
