"""Cosine similarity between face embeddings.

Pure function, numpy only, no I/O and no config -- the most-tested and least-coupled module in
the project. Keep it that way.

A cosine score is NOT a probability and NOT a confidence. 0.7123 is "cosine similarity 0.7123",
never "71% confident".
"""

from __future__ import annotations

import numpy as np

from ..errors import FaceChainError


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity in [-1.0, 1.0]."""
    a = np.asarray(a, dtype=np.float32).reshape(-1)
    b = np.asarray(b, dtype=np.float32).reshape(-1)
    if a.shape != b.shape:
        raise FaceChainError("embedding shape mismatch", {"a": a.shape[0], "b": b.shape[0]})

    na, nb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
    if na == 0.0 or nb == 0.0:
        raise FaceChainError("cannot compare a zero vector")

    return float(np.clip(np.dot(a, b) / (na * nb), -1.0, 1.0))
