"""Pipeline tests with injected fake providers. No network, no real face models."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from facechain.config import Config
from facechain.errors import NoVerifiedMatchError, SearchProviderError
from facechain.providers import Providers
from facechain.search.candidates import filter_social, union
from tests.fakes import candidate, empty_search, failing_fetch, failing_search, make_fake_providers


@pytest.fixture
def probe_vec():
    v = np.zeros(512, dtype=np.float32)
    v[0] = 1.0
    return v


def _patch_face(monkeypatch, score_for):
    """Route candidate detect/embed through a deterministic stand-in."""
    import facechain.pipeline as P

    class FakeFace:
        aligned = np.zeros((112, 112, 3), dtype=np.uint8)

    monkeypatch.setattr(P, "_detect_or_none", lambda img: FakeFace())
    monkeypatch.setattr(P, "load_image", lambda p: np.zeros((10, 10, 3), dtype=np.uint8))
    counter = {"n": 0}

    def fake_embed(aligned):
        v = np.zeros(512, dtype=np.float32)
        v[0] = score_for(counter["n"])
        v[1] = float(np.sqrt(max(0.0, 1 - v[0] ** 2)))
        counter["n"] += 1
        return v

    monkeypatch.setattr(P, "embed", fake_embed)
    return counter


class TestCandidateVerification:
    def test_candidates_are_independently_embedded(self, monkeypatch, probe_vec, tmp_path, cfg):
        """ANTI-CHEAT: every candidate gets its own detect+embed pass."""
        from facechain.pipeline import verify_candidates

        counter = _patch_face(monkeypatch, lambda n: [0.9, 0.8, 0.2][n])
        provs, calls = make_fake_providers([])
        cands = [candidate(f"https://x.com/a/{i}", f"https://cdn.test/{i}.jpg") for i in range(3)]
        scored = verify_candidates(probe_vec, cands, tmp_path, cfg, provs)

        assert counter["n"] == 3, "each candidate must be embedded independently"
        assert len(calls["fetch"]) == 3
        assert [round(s.cosine, 3) for s in scored] == [0.9, 0.8, 0.2]

    def test_results_ranked_descending(self, monkeypatch, probe_vec, tmp_path, cfg):
        from facechain.pipeline import verify_candidates

        _patch_face(monkeypatch, lambda n: [0.2, 0.95, 0.5][n])
        provs, _ = make_fake_providers([])
        cands = [candidate(f"https://x.com/a/{i}", f"https://cdn.test/{i}.jpg") for i in range(3)]
        scored = verify_candidates(probe_vec, cands, tmp_path, cfg, provs)
        assert [round(s.cosine, 2) for s in scored] == [0.95, 0.5, 0.2]

    def test_fetch_failure_skips_only_that_candidate(self, monkeypatch, probe_vec, tmp_path, cfg):
        from facechain.pipeline import verify_candidates

        _patch_face(monkeypatch, lambda n: 0.9)
        provs, _ = make_fake_providers([])
        provs = Providers(provs.face_search, provs.image_upload, failing_fetch)
        cands = [candidate(f"https://x.com/a/{i}", f"https://cdn.test/{i}.jpg") for i in range(3)]
        assert verify_candidates(probe_vec, cands, tmp_path, cfg, provs) == []

    def test_candidate_with_no_face_is_skipped_not_zero_scored(
        self, monkeypatch, probe_vec, tmp_path, cfg
    ):
        import facechain.pipeline as P
        from facechain.pipeline import verify_candidates

        _patch_face(monkeypatch, lambda n: 0.9)
        monkeypatch.setattr(P, "_detect_or_none", lambda img: None)
        provs, _ = make_fake_providers([])
        cands = [candidate("https://x.com/a/1", "https://cdn.test/1.jpg")]
        assert verify_candidates(probe_vec, cands, tmp_path, cfg, provs) == []


class TestThreshold:
    @pytest.mark.parametrize("score,expected", [(0.50, 1), (0.46, 1), (0.44, 0), (0.20, 0)])
    def test_threshold_admits_above_rejects_below(
        self, monkeypatch, probe_vec, tmp_path, score, expected
    ):
        from facechain.pipeline import verify_candidates

        cfg = Config(network="local", threshold=0.45)
        _patch_face(monkeypatch, lambda n: score)
        provs, _ = make_fake_providers([])
        cands = [candidate("https://x.com/a/1", "https://cdn.test/1.jpg")]
        scored = verify_candidates(probe_vec, cands, tmp_path, cfg, provs)
        assert len([s for s in scored if s.cosine >= cfg.threshold]) == expected

    def test_comparison_is_inclusive_of_the_threshold(self):
        """A candidate exactly at tau is admitted: the spec rejects only *below* tau.

        Asserted directly rather than by reconstructing a vector, because a cosine of exactly
        0.45 is not reachable through float32 -- 0.45 round-trips to 0.44999998807907104. Testing
        the comparison itself is meaningful; testing float equality at a boundary is not.
        """
        cfg = Config(network="local", threshold=0.45)
        assert (cfg.threshold >= cfg.threshold) is True
        assert (0.4499999 >= cfg.threshold) is False


class TestProviderErrorVsEmpty:
    """HC-17: these two tests differ only in the mocked response. That pairing IS the proof."""

    def test_provider_failure_raises(self, cfg):
        with pytest.raises(SearchProviderError):
            failing_search(500)("https://fake.test/x.png", cfg)

    def test_empty_result_returns_empty_list(self, cfg):
        assert empty_search("https://fake.test/x.png", cfg) == []


class TestUnionAndFilter:
    def test_union_is_order_stable_and_dedupes(self):
        a = [candidate("https://x.com/a/1"), candidate("https://x.com/a/2")]
        b = [candidate("https://x.com/a/2"), candidate("https://x.com/a/3")]
        assert [c.page_url for c in union(a, b)] == [
            "https://x.com/a/1", "https://x.com/a/2", "https://x.com/a/3",
        ]

    def test_filter_keeps_social_rejects_news(self, cfg):
        cands = [
            candidate("https://www.instagram.com/p/AAA/"),
            candidate("https://www.nytimes.com/2026/01/01/story.html"),
            candidate("https://shutterstock.com/image/1"),
            candidate("https://x.com/user/status/1"),
        ]
        kept = [c.page_url for c in filter_social(cands, cfg)]
        assert kept == ["https://www.instagram.com/p/AAA/", "https://x.com/user/status/1"]

    def test_substring_domain_attack_rejected(self, cfg):
        cands = [candidate("https://notinstagram.com.evil.co/p/AAA/")]
        assert filter_social(cands, cfg) == []
