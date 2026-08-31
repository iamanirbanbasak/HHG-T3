"""Lazy, process-cached loader for the InsightFace buffalo_l pack.

Never loads at import time: `facechain --help` must stay fast, and tests that never touch a face
must not pay a 300MB download. Loads exactly once per process (NFR-002).
"""

from __future__ import annotations

from functools import lru_cache

from ..errors import FaceChainError

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
        app = FaceAnalysis(name=PACK, providers=["CPUExecutionProvider"])
        app.prepare(ctx_id=-1, det_size=DET_SIZE)
    except Exception as exc:  # noqa: BLE001
        raise FaceChainError("could not load face models", {"pack": PACK, "error": str(exc)}) from exc

    _load_count += 1
    return app


def load_count() -> int:
    """How many times the models were actually loaded. Used to assert single-load."""
    return _load_count
