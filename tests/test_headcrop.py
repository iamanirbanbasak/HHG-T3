"""Head-crop tests.

This exists because a real Lens query on a photo of someone in a red kurta returned 60 results,
essentially all garment listings. The crop must exclude clothing so the matcher has only a face
to work with.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from facechain.face.headcrop import BACKGROUND, DEFAULT_SIZE, head_crop, head_region

FX = Path(__file__).parent / "fixtures"


class TestHeadRegion:
    def test_expands_beyond_the_face_box(self):
        x0, y0, x1, y1 = head_region((100, 100, 50, 60), (600, 600, 3))
        assert x0 < 100 and y0 < 100
        assert x1 > 150 and y1 > 160

    def test_grows_more_upward_than_downward(self):
        """Downward growth adds collar and shoulders -- the clothing we want excluded."""
        x, y, w, h = 100, 100, 50, 60
        _, y0, _, y1 = head_region((x, y, w, h), (600, 600, 3))
        assert (y - y0) > (y1 - (y + h))

    def test_clamped_to_image_bounds(self):
        x0, y0, x1, y1 = head_region((0, 0, 40, 40), (100, 100, 3))
        assert x0 >= 0 and y0 >= 0 and x1 <= 100 and y1 <= 100

    def test_face_at_edge_does_not_invert(self):
        x0, y0, x1, y1 = head_region((90, 90, 20, 20), (100, 100, 3))
        assert x1 > x0 and y1 > y0


class TestHeadCrop:
    @pytest.fixture(scope="class")
    def real_face(self):
        from facechain.face.detect import detect_probe, load_image

        img = load_image(FX / "faces_multi.jpg")
        probe, _ = detect_probe(img)
        return img, probe

    def test_output_is_square_and_requested_size(self, real_face):
        img, probe = real_face
        out = head_crop(img, probe.bbox)
        assert out.shape == (DEFAULT_SIZE, DEFAULT_SIZE, 3)

    def test_custom_size(self, real_face):
        img, probe = real_face
        assert head_crop(img, probe.bbox, size=256).shape == (256, 256, 3)

    def test_much_larger_than_the_arcface_crop(self, real_face):
        """A 112px query gives a reverse-image engine almost nothing to match on."""
        img, probe = real_face
        assert head_crop(img, probe.bbox).shape[0] > probe.aligned.shape[0] * 3

    def test_corners_are_background_after_removal(self, real_face):
        img, probe = real_face
        out = head_crop(img, probe.bbox, remove_background=True)
        for y, x in [(4, 4), (4, -5), (-5, 4), (-5, -5)]:
            assert np.allclose(out[y, x], BACKGROUND, atol=6), "corner should be neutral"

    def test_centre_retains_the_face(self, real_face):
        img, probe = real_face
        out = head_crop(img, probe.bbox, remove_background=True)
        c = out[DEFAULT_SIZE // 2, DEFAULT_SIZE // 2]
        assert not np.allclose(c, BACKGROUND, atol=6), "centre must not be masked away"

    def test_background_removal_can_be_disabled(self, real_face):
        img, probe = real_face
        kept = head_crop(img, probe.bbox, remove_background=False)
        removed = head_crop(img, probe.bbox, remove_background=True)
        assert not np.array_equal(kept, removed)

    def test_deterministic(self, real_face):
        img, probe = real_face
        assert np.array_equal(head_crop(img, probe.bbox), head_crop(img, probe.bbox))

    def test_the_crop_still_contains_a_detectable_face(self, real_face):
        """A masked crop that the detector can no longer read would be useless as a query."""
        from facechain.face.detect import detect_faces

        img, probe = real_face
        assert len(detect_faces(head_crop(img, probe.bbox))) >= 1

    def test_identity_is_preserved_through_the_crop(self, real_face):
        """The head crop must still be the same person, or it is not a valid query."""
        from facechain.face.detect import detect_probe
        from facechain.face.embed import embed
        from facechain.face.similarity import cosine

        img, probe = real_face
        cropped, _ = detect_probe(head_crop(img, probe.bbox))
        assert cosine(embed(probe.aligned), embed(cropped.aligned)) > 0.7

    def test_degenerate_bbox_raises(self, real_face):
        img, _ = real_face
        with pytest.raises(ValueError):
            head_crop(img, (0, 0, 0, 0))
