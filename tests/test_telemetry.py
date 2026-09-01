"""The onnxruntime wheel must not phone home, and must not abort the process on the way out.

The macOS onnxruntime wheel embeds Microsoft's 1DS telemetry SDK, which uploads to
mobile.events.data.microsoft.com from a background thread. Beyond the privacy problem for a tool
that scans local photos, its teardown races interpreter shutdown and aborts the process with
SIGABRT after the real exit code was already chosen.

The kill switch is an environment variable read when onnxruntime is imported, so these tests
check the two things that make it work: it is set, and it is set early enough.
"""

from __future__ import annotations

import os
import subprocess
import sys


def _probe(code: str, env_extra: dict[str, str] | None = None) -> str:
    env = dict(os.environ)
    env.pop("ORT_DISABLE_TELEMETRY", None)
    env.update(env_extra or {})
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, env=env, check=True
    )
    return out.stdout.strip()


def test_importing_facechain_disables_onnxruntime_telemetry():
    assert _probe("import os, facechain; print(os.environ['ORT_DISABLE_TELEMETRY'])") == "1"


def test_guard_runs_before_onnxruntime_is_imported():
    """Set after the import, the variable has no effect -- onnxruntime reads it at module init."""
    assert _probe("import sys, facechain; print('onnxruntime' in sys.modules)") == "False"


def test_explicit_setting_wins():
    """An operator who wants stock behaviour can have it: the guard is a setdefault."""
    probe = "import os, facechain; print(os.environ['ORT_DISABLE_TELEMETRY'])"
    assert _probe(probe, {"ORT_DISABLE_TELEMETRY": "0"}) == "0"
