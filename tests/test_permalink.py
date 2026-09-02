"""Resolving an Instagram post permalink to the publishing account."""

from __future__ import annotations

from facechain.config import Config
from facechain.search.lens import Candidate
from facechain.search.permalink import handle_from_html, handle_from_text, resolve_owner


def test_title_photo_by():
    assert handle_from_text("Photo by jane.doe on Instagram") == "jane.doe"


def test_title_on_instagram():
    assert handle_from_text('jane_doe on Instagram: "hello"') == "jane_doe"


def test_serpapi_source_line_when_title_is_the_caption():
    assert handle_from_text("Instagram \u00b7 jane.doe") == "jane.doe"
    assert handle_from_text("Instagram · jane.doe") == "jane.doe"
    assert handle_from_text("Instagram • jane.doe") == "jane.doe"
    caption = "7 hours on the clock, top 30 minds in the room"
    assert handle_from_text(f"{caption}\nInstagram · jane.doe") == "jane.doe"


def test_google_breadcrumb_is_the_owner():
    assert handle_from_text("www.instagram.com › jane.doe") == "jane.doe"


def test_shortcode_alone_is_not_a_handle():
    cand = Candidate(
        page_url="https://www.instagram.com/p/DcG3rbAFFA3/",
        image_url="https://cdn.test/i.jpg",
        title="Instagram",
        source="Instagram",
    )
    assert resolve_owner(cand, None, Config()) is None


def test_does_not_invent_from_reserved_words():
    assert handle_from_text("Photo by Instagram") is None
    assert handle_from_text("video by official on Instagram") is None
    assert handle_from_text("Instagram · login") is None
    assert handle_from_text("Instagram · accounts") is None


def test_html_login_wall_is_not_an_account():
    html = '<script src="https://www.instagram.com/rsrc.php/v3/foo.js"></script>'
    assert handle_from_html(html) is None


def test_html_owner_json():
    html = '{"owner":{"id":"1","username":"jane.doe","is_private":false}}'
    assert handle_from_html(html) == "jane.doe"


def test_google_title_for_the_same_post_is_the_owner():
    from facechain.search.websearch import owner_from_search

    body = {
        "organic_results": [
            {
                "title": "other.person on Instagram: leftover",
                "link": "https://www.instagram.com/p/OTHER/",
            },
            {
                "title": 'realuser on Instagram: "a caption"',
                "link": "https://www.instagram.com/p/DcG3rbAFFA3/",
            },
        ]
    }
    assert owner_from_search(body, "https://www.instagram.com/p/DcG3rbAFFA3/") == "realuser"


def test_google_source_when_title_is_only_the_caption():
    from facechain.search.websearch import owner_from_search

    body = {
        "organic_results": [
            {
                "title": "7 hours on the clock, top 30 minds in the room, and an ...",
                "source": "Instagram · jane.doe",
                "displayed_link": "460+ likes · 2 weeks ago",
                "snippet": "Wrapped up PwC Launchpad. Thanks @someone.else",
                "link": "https://www.instagram.com/p/DcG3rbAFFA3/",
            },
        ]
    }
    assert owner_from_search(body, "https://www.instagram.com/p/DcG3rbAFFA3/") == "jane.doe"


def test_oembed_author_name(cfg: Config):
    cand = Candidate(
        page_url="https://www.instagram.com/p/AAA/",
        image_url="https://cdn.test/i.jpg",
        title="",
        source="",
    )

    def fetch_page(url, c):
        if "rsrc.php" in url or url.endswith("/p/AAA/"):
            return '<script src="https://www.instagram.com/rsrc.php/v3/x.js"></script>'
        assert "oembed" in url
        return '{"author_name":"jane.doe","author_url":"https://www.instagram.com/jane.doe/"}'

    assert resolve_owner(cand, fetch_page, cfg) == "jane.doe"


def test_url_profile_wins_over_title(cfg: Config):
    cand = Candidate(
        page_url="https://www.instagram.com/realuser/",
        image_url="https://cdn.test/i.jpg",
        title="Photo by other.person on Instagram",
        source="",
    )
    assert resolve_owner(cand, None, cfg) == "realuser"


def test_permalink_title_unlocks_handle_expand(monkeypatch, cfg: Config, tmp_path):
    from pathlib import Path

    import numpy as np

    import facechain.pipeline as P
    from facechain.pipeline import ScoredCandidate, _expand_same_handle
    from facechain.providers import Providers
    from tests.fakes import make_fake_providers

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

    cand = Candidate(
        page_url="https://www.instagram.com/p/AAA/",
        image_url="https://cdn.test/i.jpg",
        title="Photo by jane on Instagram",
        source="Instagram",
    )
    owner = resolve_owner(cand, None, cfg)
    assert owner == "jane"
    provs, _ = make_fake_providers([])
    provs = Providers(
        provs.face_search, provs.image_upload, provs.fetch_image,
        lambda u, c: "<html></html>",
    )
    top = ScoredCandidate(candidate=cand, cosine=0.91, image_path=Path("x"))
    expanded = _expand_same_handle(probe, top, [top], tmp_path, cfg, provs, handle=owner)
    assert any("github.com/jane" in s.candidate.page_url for s in expanded)
