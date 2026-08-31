from __future__ import annotations

import numpy as np
import pytest

from facechain.errors import FaceChainError
from facechain.face.embed import l2_normalise
from facechain.face.similarity import cosine


def _unit(i: int, dim: int = 512) -> np.ndarray:
    v = np.zeros(dim, dtype=np.float32)
    v[i] = 1.0
    return v


class TestCosine:
    def test_identical_vectors_score_one(self):
        v = _unit(0)
        assert cosine(v, v) == pytest.approx(1.0, abs=1e-6)

    def test_orthogonal_vectors_score_zero(self):
        assert cosine(_unit(0), _unit(1)) == pytest.approx(0.0, abs=1e-6)

    def test_opposite_vectors_score_minus_one(self):
        assert cosine(_unit(0), -_unit(0)) == pytest.approx(-1.0, abs=1e-6)

    def test_symmetric(self):
        rng = np.random.default_rng(7)
        a = rng.normal(size=512).astype(np.float32)
        b = rng.normal(size=512).astype(np.float32)
        assert cosine(a, b) == pytest.approx(cosine(b, a), abs=1e-6)

    def test_always_bounded(self):
        rng = np.random.default_rng(11)
        for _ in range(200):
            a = rng.normal(size=64).astype(np.float32)
            b = rng.normal(size=64).astype(np.float32)
            assert -1.0 <= cosine(a, b) <= 1.0

    def test_invariant_to_scaling(self):
        rng = np.random.default_rng(3)
        a = rng.normal(size=128).astype(np.float32)
        b = rng.normal(size=128).astype(np.float32)
        assert cosine(a, b) == pytest.approx(cosine(a * 7.5, b * 0.2), abs=1e-5)

    def test_shape_mismatch_raises(self):
        with pytest.raises(FaceChainError):
            cosine(np.zeros(512, dtype=np.float32), np.zeros(128, dtype=np.float32))

    def test_zero_vector_raises(self):
        with pytest.raises(FaceChainError):
            cosine(np.zeros(512, dtype=np.float32), _unit(0))


class TestL2Normalise:
    def test_produces_unit_norm(self):
        rng = np.random.default_rng(5)
        v = l2_normalise(rng.normal(size=512).astype(np.float32))
        assert float(np.linalg.norm(v)) == pytest.approx(1.0, abs=1e-5)

    def test_preserves_direction(self):
        rng = np.random.default_rng(9)
        v = rng.normal(size=512).astype(np.float32)
        assert cosine(v, l2_normalise(v)) == pytest.approx(1.0, abs=1e-5)

    def test_zero_vector_raises(self):
        with pytest.raises(FaceChainError):
            l2_normalise(np.zeros(512, dtype=np.float32))
