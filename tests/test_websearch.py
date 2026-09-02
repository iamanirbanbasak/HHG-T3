"""LinkedIn profile search from a verified handle. No network."""

from __future__ import annotations

from pathlib import Path

from facechain.config import Config
from facechain.search.websearch import parse_linkedin_results, search_linkedin


def test_keeps_profile_urls_and_drops_jobs_and_companies():
    body = {
        "organic_results": [
            {
                "title": "Jane Doe - Engineer",
                "link": "https://www.linkedin.com/in/jane-doe",
                "thumbnail": "https://cdn.test/jane.jpg",
            },
            {
                "title": "Jobs",
                "link": "https://www.linkedin.com/jobs/view/123",
                "thumbnail": "https://cdn.test/j.jpg",
            },
            {
                "title": "Acme",
                "link": "https://www.linkedin.com/company/acme",
                "thumbnail": "https://cdn.test/c.jpg",
            },
            {
                "title": "Post",
                "link": "https://www.linkedin.com/posts/jane-doe-activity-1",
            },
            {
                "title": "IN locale",
                "link": "https://in.linkedin.com/in/jane-doe-2",
                "thumbnail": "https://cdn.test/in.jpg",
            },
        ]
    }
    got = parse_linkedin_results(body)
    urls = [c.page_url for c in got]
    assert urls == [
        "https://www.linkedin.com/in/jane-doe",
        "https://in.linkedin.com/in/jane-doe-2",
    ]
    assert got[0].image_url.endswith("jane.jpg")
    assert got[0].source == "linkedin-search"


def test_search_without_a_key_is_a_no_op(cfg: Config):
    assert search_linkedin("jane", cfg) == []


def test_expand_face_scores_linkedin_search_hits(monkeypatch, cfg: Config, tmp_path: Path):
    import numpy as np

    import facechain.pipeline as P
    from facechain.pipeline import ScoredCandidate, _expand_same_handle
    from facechain.providers import Providers
    from tests.fakes import candidate, make_fake_providers

    class FakeFace:
        aligned = np.zeros((112, 112, 3), dtype=np.uint8)

    monkeypatch.setattr(P, "_detect_or_none", lambda img: FakeFace())
    monkeypatch.setattr(P, "load_image", lambda p: np.zeros((10, 10, 3), dtype=np.uint8))

    def fake_embed(aligned):
        v = np.zeros(512, dtype=np.float32)
        v[0] = 0.8
        v[1] = float(np.sqrt(1 - 0.8 ** 2))
        return v

    monkeypatch.setattr(P, "embed", fake_embed)
    probe = np.zeros(512, dtype=np.float32)
    probe[0] = 1.0

    li = candidate(
        "https://www.linkedin.com/in/jane-doe",
        "https://cdn.test/li.jpg",
    )

    def web_search(handle, cfg):
        assert handle == "jane"
        return [li]

    provs, _ = make_fake_providers([])
    provs = Providers(
        provs.face_search, provs.image_upload, provs.fetch_image,
        lambda url, c: "<html></html>", web_search,
    )
    top = ScoredCandidate(
        candidate=candidate("https://www.instagram.com/jane/"),
        cosine=0.91, image_path=Path("x"),
    )
    expanded = _expand_same_handle(probe, top, [top], tmp_path, cfg, provs)
    urls = {s.candidate.page_url for s in expanded}
    assert "https://www.linkedin.com/in/jane-doe" in urls
