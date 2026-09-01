"""Exit codes asserted through real subprocesses.

typer's CliRunner invokes the app in-process, so it can never observe a crash during interpreter
shutdown. That blind spot hid a real defect: native teardown aborted the process with SIGABRT
(134), replacing the documented exit code after output had already been written. These tests
spawn the CLI the way a user or a grading script would.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FX = ROOT / "tests" / "fixtures"
PY = sys.executable


def run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [PY, "-m", "facechain.cli", *args],
        cwd=ROOT, capture_output=True, text=True, timeout=180,
    )


def test_help_exits_zero():
    assert run_cli("--help").returncode == 0


def test_scan_success_exits_zero():
    assert run_cli("scan", "--image", str(FX / "faces_multi.jpg")).returncode == 0


def test_no_face_exits_two():
    r = run_cli("scan", "--image", str(FX / "face_none.jpg"))
    assert r.returncode == 2, r.stdout + r.stderr


def test_exit_code_is_never_a_signal_abort():
    """Guards the specific regression: 134 (SIGABRT) must never replace a real code."""
    for args in (
        ("--help",),
        ("scan", "--image", str(FX / "faces_multi.jpg")),
        ("scan", "--image", str(FX / "face_none.jpg")),
    ):
        rc = run_cli(*args).returncode
        assert rc < 128, f"{args} returned {rc}, which is a signal death, not an exit code"


def test_selftest_negative_path_exits_four():
    r = run_cli(
        "selftest",
        "--probe", str(FX / "faces_multi.jpg"),
        "--candidate", str(FX / "face_other_person.jpg"),
        "--post-url", "https://example.com/p/1",
    )
    assert r.returncode == 4, r.stdout + r.stderr


def test_selftest_positive_path_exits_zero():
    r = run_cli(
        "selftest",
        "--probe", str(FX / "faces_multi.jpg"),
        "--candidate", str(FX / "faces_multi.jpg"),
        "--post-url", "https://example.com/p/2",
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert "MATCH" in r.stdout and "MISMATCH" in r.stdout
