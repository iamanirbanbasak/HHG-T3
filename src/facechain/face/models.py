"""Lazy, process-cached loader for the InsightFace buffalo_l pack.

Never loads at import time: `facechain --help` must stay fast, and tests that never touch a face
must not pay a 300MB download. Loads exactly once per process (NFR-002).
"""

from __future__ import annotations

from functools import lru_cache

import contextlib
import io
import sys
import warnings

from ..errors import FaceChainError

# Presentation-only switch, set by the CLI. Deliberately NOT read from the environment: config.py
# is the single place this project reads os.environ (FR-054), and the import-graph test enforces
# it. Defaults to quiet because the CLI is the only UI.
_verbose = False


def set_verbose(value: bool) -> None:
    global _verbose
    _verbose = bool(value)


@contextlib.contextmanager
def _quiet_stdout():
    """Silence third-party model-load banners."""
    if _verbose:
        yield
        return
    saved = sys.stdout
    sys.stdout = io.StringIO()
    try:
        yield
    finally:
        sys.stdout = saved

PACK = "buffalo_l"
DET_SIZE = (640, 640)

_load_count = 0


@lru_cache(maxsize=1)
def get_app():
    """Return the cached FaceAnalysis app.

    First call downloads ~300MB of models to ~/.insightface. Pre-warm before a live demo.
    """
    global _load_count
    try:
        from insightface.app import FaceAnalysis
    except ImportError as exc:  # pragma: no cover
        raise FaceChainError(
            "insightface is not installed",
            {"hint": "uv sync, or uv pip install insightface onnxruntime"},
        ) from exc

    try:
        # InsightFace prints per-model banners to stdout on load. Harmless, but it makes the CLI
        # illegible in a screen recording -- and the recording is this project's only UI.
        with _quiet_stdout():
            app = FaceAnalysis(name=PACK, providers=["CPUExecutionProvider"])
            app.prepare(ctx_id=-1, det_size=DET_SIZE)
        _silence_upstream_warnings()
    except Exception as exc:  # noqa: BLE001
        raise FaceChainError("could not load face models", {"pack": PACK, "error": str(exc)}) from exc

    _load_count += 1
    return app


def load_count() -> int:
    """How many times the models were actually loaded. Used to assert single-load."""
    return _load_count


def _silence_upstream_warnings() -> None:
    """Mute FutureWarnings raised inside insightface itself.

    insightface calls np.linalg.lstsq without rcond and uses a deprecated scikit-image estimate
    API, emitting two warnings per aligned face. That is noise we cannot fix from here -- it is
    upstream code -- and it drowns the CLI output the demo depends on. Scoped to insightface
    modules so warnings from our own code still surface.
    """
    for module in (r"insightface\..*",):
        warnings.filterwarnings("ignore", category=FutureWarning, module=module)
        warnings.filterwarnings("ignore", category=DeprecationWarning, module=module)
