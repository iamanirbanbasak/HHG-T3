"""Extracting social/profile links from a face-verified page."""

from __future__ import annotations

from pathlib import Path

from facechain.config import Config
from facechain.pipeline import ScoredCandidate, _linked_from_verified_page
from facechain.providers import Providers
from facechain.search.candidates import is_core_social
from facechain.search.page_links import (
    extract_hub_links,
    extract_profile_links,
    og_image,
    profile_guesses,
)
from tests.fakes import candidate, make_fake_providers

PORTFOLIO = "https://www.devfolio.co/@jane/projects"

HTML = """
<html><body>
  <a href="https://github.com/jane">GitHub</a>
  <a href="https://www.linkedin.com/in/jane-doe">LinkedIn</a>
  <a href="https://x.com/intent/tweet?url=https://example.com">share</a>
  <a href="https://www.devfolio.co/@jane">same host</a>
  <a href="https://assets.devfolio.co/logo.svg">asset</a>
  <a href="https://api.devfolio.co/api/hotfix/css/all.css">css</a>
  <a href="/relative-internal">no</a>
  <script>{"profile":"https://github.com/jane","twitter":"https://x.com/jane"}</script>
</body></html>
"""


def test_extracts_allowlisted_links_and_skips_noise(cfg: Config):
    urls = extract_profile_links(HTML, PORTFOLIO, cfg)
    assert "https://github.com/jane" in urls
    assert "https://www.linkedin.com/in/jane-doe" in urls
    assert "https://x.com/jane" in urls
    assert not any("intent" in u for u in urls)
    assert not any("devfolio.co" in u for u in urls)
    assert not any(u.endswith(".css") or u.endswith(".svg") for u in urls)


def test_github_is_not_core_social(cfg: Config):
    assert is_core_social("https://www.instagram.com/p/AAA/", cfg)
    assert is_core_social("https://www.linkedin.com/in/jane/", cfg)
    assert not is_core_social("https://github.com/jane", cfg)
    assert not is_core_social(PORTFOLIO, cfg)


def test_enrichment_when_only_a_portfolio_survived(cfg: Config):
    provs, _ = make_fake_providers([])
    provs = Providers(
        provs.face_search, provs.image_upload, provs.fetch_image,
        lambda url, c: HTML,
    )
    top = ScoredCandidate(
        candidate=candidate(PORTFOLIO), cosine=0.94, image_path=Path("x"),
    )
    linked = _linked_from_verified_page(top, [top], cfg, provs)
    by_platform = {a.platform: a for a in linked}
    assert by_platform["github"].handle == "jane"
    assert by_platform["linkedin"].handle == "jane-doe"
    assert by_platform["x"].handle == "jane"
    assert all(a.origin == "linked" for a in linked)


def test_enrichment_from_an_instagram_profile(cfg: Config):
    """Instagram is a core social; we still read the page for outbound socials."""
    provs, _ = make_fake_providers([])
    provs = Providers(
        provs.face_search, provs.image_upload, provs.fetch_image,
        lambda url, c: HTML,
    )
    top = ScoredCandidate(
        candidate=candidate("https://www.instagram.com/jane/"),
        cosine=0.91, image_path=Path("x"),
    )
    linked = _linked_from_verified_page(top, [top], cfg, provs)
    platforms = {a.platform for a in linked}
    assert "github" in platforms and "linkedin" in platforms


def test_page_fetch_failure_does_not_fail_the_run(cfg: Config):
    def boom(url, cfg):
        raise RuntimeError("timeout")

    provs, _ = make_fake_providers([])
    provs = Providers(provs.face_search, provs.image_upload, provs.fetch_image, boom)
    top = ScoredCandidate(
        candidate=candidate(PORTFOLIO), cosine=0.94, image_path=Path("x"),
    )
    assert _linked_from_verified_page(top, [top], cfg, provs) == []


def test_linkedin_claim_kept_when_page_is_blocked(cfg: Config):
    from facechain.pipeline import _linkedin_claim
    from facechain.search.candidates import normalise_url

    known = {normalise_url("https://www.instagram.com/jane")}
    linked = _linkedin_claim("jane", known)
    assert len(linked) == 1
    assert linked[0].platform == "linkedin"
    assert linked[0].origin == "linked"
    assert any("linkedin.com/in/jane" in u for u in linked[0].urls)


def test_linkedin_claim_not_duplicated_if_already_known(cfg: Config):
    from facechain.pipeline import _linkedin_claim
    from facechain.search.candidates import normalise_url

    known = {normalise_url("https://www.linkedin.com/in/jane")}
    assert _linkedin_claim("jane", known) == []


def test_skips_enrichment_when_fetch_page_is_unset(cfg: Config):
    provs, _ = make_fake_providers([])
    top = ScoredCandidate(
        candidate=candidate(PORTFOLIO), cosine=0.94, image_path=Path("x"),
    )
    assert _linked_from_verified_page(top, [top], cfg, provs) == []


def test_profile_guesses_skip_source_platform_and_invalid_github():
    gh = {p: page for p, page, _ in profile_guesses("jane", "instagram")}
    assert "github" in gh and gh["github"].endswith("/jane")
    assert "linkedin" in gh and "/in/jane" in gh["linkedin"]
    assert all(p != "instagram" for p, _, _ in profile_guesses("jane", "instagram"))
    assert "github" not in {p for p, _, _ in profile_guesses("jane_doe", "instagram")}
    assert "linkedin" not in {p for p, _, _ in profile_guesses("jane_doe", "instagram")}


def test_og_image_reads_meta():
    html = '<meta property="og:image" content="https://cdn.example.com/a.jpg" />'
    assert og_image(html, "https://example.com/") == "https://cdn.example.com/a.jpg"


def test_extract_hub_links():
    html = '<a href="https://linktr.ee/jane">bio</a><a href="https://github.com/jane">gh</a>'
    assert extract_hub_links(html, "https://www.instagram.com/jane/") == [
        "https://linktr.ee/jane",
    ]


def test_same_handle_github_is_face_scored(monkeypatch, cfg: Config, tmp_path: Path):
    import numpy as np

    import facechain.pipeline as P
    from facechain.pipeline import _expand_same_handle

    class FakeFace:
        aligned = np.zeros((112, 112, 3), dtype=np.uint8)

    monkeypatch.setattr(P, "_detect_or_none", lambda img: FakeFace())
    monkeypatch.setattr(P, "load_image", lambda p: np.zeros((10, 10, 3), dtype=np.uint8))

    def fake_embed(aligned):
        v = np.zeros(512, dtype=np.float32)
        v[0] = 0.9
        v[1] = float(np.sqrt(1 - 0.9 ** 2))
        return v

    monkeypatch.setattr(P, "embed", fake_embed)
    probe = np.zeros(512, dtype=np.float32)
    probe[0] = 1.0

    html = {
        "https://www.youtube.com/@jane":
            '<meta property="og:image" content="https://cdn.test/yt.jpg" />',
    }

    def fetch_page(url, c):
        if url.startswith("https://github.com/"):
            raise AssertionError("github should use the png avatar, not HTML")
        return html.get(url, "<html></html>")

    provs, _ = make_fake_providers([])
    provs = Providers(provs.face_search, provs.image_upload, provs.fetch_image, fetch_page)
    top = ScoredCandidate(
        candidate=candidate("https://www.instagram.com/jane/"),
        cosine=0.91, image_path=Path("x"),
    )
    expanded = _expand_same_handle(probe, top, [top], tmp_path, cfg, provs)
    urls = {s.candidate.page_url for s in expanded}
    assert any(u.startswith("https://github.com/jane") for u in urls)
    assert all(s.cosine >= cfg.threshold for s in expanded)

