"""Face detection and embedding against real models.

Fixtures are the sample images bundled with the insightface package -- no scraped faces, no
private individuals, no consent question.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from facechain.errors import FaceChainError, NoFaceDetectedError
from facechain.face.detect import detect_faces, detect_probe, load_image
from facechain.face.embed import DIM, embed, embedding_digest
from facechain.face.similarity import cosine

FX = Path(__file__).parent / "fixtures"
MULTI, NONE_ = FX / "faces_multi.jpg", FX / "face_none.jpg"
ALIGNED, MALFORMED, EMPTY = FX / "aligned_112.png", FX / "malformed.jpg", FX / "empty.jpg"

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


@pytest.fixture(scope="module")
def multi_img():
    return load_image(MULTI)


class TestLoadImage:
    def test_loads_jpeg(self):
        assert load_image(MULTI).ndim == 3

    def test_loads_png(self):
        assert load_image(ALIGNED).shape == (112, 112, 3)

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FaceChainError):
            load_image(tmp_path / "nope.jpg")

    def test_empty_file_raises(self):
        with pytest.raises(FaceChainError):
            load_image(EMPTY)

    def test_malformed_file_raises(self):
        with pytest.raises(FaceChainError):
            load_image(MALFORMED)


class TestDetection:
    def test_detects_faces(self, multi_img):
        faces = detect_faces(multi_img)
        assert len(faces) >= 2
        assert all(f.det_score > 0.5 for f in faces)

    def test_sorted_by_score_descending(self, multi_img):
        scores = [f.det_score for f in detect_faces(multi_img)]
        assert scores == sorted(scores, reverse=True)

    def test_probe_is_the_highest_scoring_face(self, multi_img):
        probe, n = detect_probe(multi_img)
        assert probe.det_score == max(f.det_score for f in detect_faces(multi_img))
        assert n >= 2

    def test_records_multiple_face_count(self, multi_img):
        _, n = detect_probe(multi_img)
        assert n == len(detect_faces(multi_img))

    def test_no_face_returns_empty_list(self):
        assert detect_faces(load_image(NONE_)) == []

    def test_no_face_probe_raises(self):
        """Never fabricate a detection to keep a run alive."""
        with pytest.raises(NoFaceDetectedError):
            detect_probe(load_image(NONE_))

    def test_bbox_is_positive(self, multi_img):
        probe, _ = detect_probe(multi_img)
        assert probe.bbox[2] > 0 and probe.bbox[3] > 0


class TestAlignment:
    def test_output_shape(self, multi_img):
        probe, _ = detect_probe(multi_img)
        assert probe.aligned.shape == (112, 112, 3)

    def test_alignment_is_deterministic(self, multi_img):
        """The aligned crop is hashed into the evidence chain, so it must be byte-stable."""
        a = detect_probe(multi_img)[0].aligned
        b = detect_probe(load_image(MULTI))[0].aligned
        assert np.array_equal(a, b)


class TestEmbedding:
    def test_shape_and_dtype(self, multi_img):
        v = embed(detect_probe(multi_img)[0].aligned)
        assert v.shape == (DIM,) and v.dtype == np.float32

    def test_is_l2_normalised(self, multi_img):
        """get_feat returns an unnormalised vector; normalising is load-bearing, not cosmetic."""
        v = embed(detect_probe(multi_img)[0].aligned)
        assert float(np.linalg.norm(v)) == pytest.approx(1.0, abs=1e-5)

    def test_deterministic(self, multi_img):
        probe, _ = detect_probe(multi_img)
        assert np.allclose(embed(probe.aligned), embed(probe.aligned), atol=1e-6)

    def test_works_on_a_prealigned_crop(self):
        v = embed(load_image(ALIGNED))
        assert v.shape == (DIM,)

    def test_wrong_shape_raises(self):
        with pytest.raises(FaceChainError):
            embed(np.zeros((64, 64, 3), dtype=np.uint8))

    def test_digest_is_stable_and_hex(self, multi_img):
        v = embed(detect_probe(multi_img)[0].aligned)
        d = embedding_digest(v)
        assert len(d) == 64 and d == embedding_digest(v)


class TestDiscrimination:
    """Same face scores far above different faces. Smoke check, not calibration (M12 owns that)."""

    def test_same_face_outscores_different_faces(self, multi_img):
        faces = detect_faces(multi_img)
        assert len(faces) >= 2
        v0 = embed(faces[0].aligned)
        same = cosine(v0, embed(faces[0].aligned))
        diff = cosine(v0, embed(faces[1].aligned))
        assert same == pytest.approx(1.0, abs=1e-5)
        assert diff < same
        print(f"\n  same-face cosine={same:.4f}  different-face cosine={diff:.4f}")


class TestModelLoadedOnce:
    def test_single_load_across_many_detections(self, multi_img):
        from facechain.face.models import load_count

        before = load_count()
        for _ in range(3):
            detect_faces(multi_img)
        assert load_count() == before
