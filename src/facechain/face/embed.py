"""ArcFace embedding.

Returns a 512-d L2-normalised float32 vector. Normalisation is not cosmetic: cosine similarity on
unnormalised vectors is a silent correctness bug that would distort every threshold decision
downstream.
"""

from __future__ import annotations

import hashlib

import numpy as np

from ..errors import FaceChainError

DIM = 512


def embed(aligned: np.ndarray) -> np.ndarray:
    """Embed a 112x112 aligned crop into a normalised 512-d vector."""
    if aligned is None or aligned.ndim != 3 or aligned.shape[:2] != (112, 112):
        raise FaceChainError(
            "expected a (112, 112, 3) aligned crop",
            {"got": str(None if aligned is None else aligned.shape)},
        )

    from .models import get_app

    rec = get_app().models["recognition"]
    vec = np.asarray(rec.get_feat(aligned), dtype=np.float32).reshape(-1)
    if vec.shape[0] != DIM:
        raise FaceChainError("unexpected embedding size", {"got": int(vec.shape[0])})
    return l2_normalise(vec)


def l2_normalise(vec: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vec))
    if norm == 0.0:
        raise FaceChainError("cannot normalise a zero vector")
    return (vec / norm).astype(np.float32)


def embedding_digest(vec: np.ndarray) -> str:
    """SHA-256 of the embedding bytes.

    The bundle stores this digest, never the embedding itself -- embeddings are biometric data and
    nothing in the design requires persisting them.
    """
    return hashlib.sha256(np.asarray(vec, dtype=np.float32).tobytes()).hexdigest()
