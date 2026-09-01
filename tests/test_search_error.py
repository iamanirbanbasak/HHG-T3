"""HC-17: a provider failure must never be reportable as an empty result.

The two classes below differ only in the mocked HTTP response. That pairing is the proof; a
single test cannot demonstrate a distinction.
"""

from __future__ import annotations

import httpx
import pytest

from facechain.config import Config
from facechain.errors import SearchProviderError
from facechain.search.lens import parse_candidates, search
from facechain.search.uploader import upload


class _Resp:
    def __init__(self, status: int, body=None, text: str = ""):
        self.status_code, self._body, self.text = status, body, text

    def json(self):
        if self._body is None:
            raise ValueError("not json")
        return self._body


@pytest.fixture
def cfg_keys():
    return Config(serpapi_key="k", imgbb_key="k")


class TestProviderFailureRaises:
    @pytest.mark.parametrize("status", [400, 401, 403, 429, 500, 502, 503])
    def test_non_200_raises(self, monkeypatch, cfg_keys, status):
        monkeypatch.setattr(httpx, "get", lambda *a, **k: _Resp(status, {}))
        with pytest.raises(SearchProviderError):
            search("https://x/i.png", cfg_keys)

    def test_timeout_raises(self, monkeypatch, cfg_keys):
        def boom(*a, **k):
            raise httpx.TimeoutException("timed out")

        monkeypatch.setattr(httpx, "get", boom)
        with pytest.raises(SearchProviderError):
            search("https://x/i.png", cfg_keys)

    def test_malformed_json_raises(self, monkeypatch, cfg_keys):
        monkeypatch.setattr(httpx, "get", lambda *a, **k: _Resp(200, None))
        with pytest.raises(SearchProviderError):
            search("https://x/i.png", cfg_keys)

    def test_error_field_in_body_raises(self, monkeypatch, cfg_keys):
        monkeypatch.setattr(httpx, "get", lambda *a, **k: _Resp(200, {"error": "bad key"}))
        with pytest.raises(SearchProviderError):
            search("https://x/i.png", cfg_keys)


class TestEmptyResultIsNotAnError:
    """Same code path, successful response, no matches. Must return [] and not raise."""

    def test_empty_visual_matches_returns_empty_list(self, monkeypatch, cfg_keys):
        monkeypatch.setattr(httpx, "get", lambda *a, **k: _Resp(200, {"visual_matches": []}))
        assert search("https://x/i.png", cfg_keys) == []

    def test_no_matches_key_at_all_returns_empty_list(self, monkeypatch, cfg_keys):
        monkeypatch.setattr(httpx, "get", lambda *a, **k: _Resp(200, {"search_metadata": {}}))
        assert search("https://x/i.png", cfg_keys) == []


class TestSecretsNeverLeak:
    def test_api_key_absent_from_error_message(self, monkeypatch):
        cfg = Config(serpapi_key="SUPERSECRETKEY987")
        monkeypatch.setattr(httpx, "get", lambda *a, **k: _Resp(401, {}))
        with pytest.raises(SearchProviderError) as e:
            search("https://x/i.png", cfg)
        assert "SUPERSECRETKEY987" not in str(e.value)
        assert "401" in str(e.value)

    def test_upload_key_absent_from_error_message(self, monkeypatch, tmp_path):
        p = tmp_path / "i.png"
        p.write_bytes(b"x")
        cfg = Config(imgbb_key="UPLOADSECRET456")
        monkeypatch.setattr(httpx, "post", lambda *a, **k: _Resp(403, {}))
        with pytest.raises(SearchProviderError) as e:
            upload(p, cfg)
        assert "UPLOADSECRET456" not in str(e.value)


class TestParsing:
    def test_parses_visual_matches(self):
        body = {"visual_matches": [
            {"link": "https://instagram.com/p/A/", "thumbnail": "https://c/t.jpg",
             "title": "t", "source": "Instagram"}]}
        got = parse_candidates(body)
        assert len(got) == 1 and got[0].page_url == "https://instagram.com/p/A/"

    def test_skips_entries_without_a_link(self):
        assert parse_candidates({"visual_matches": [{"title": "no link"}]}) == []

    def test_tolerates_unexpected_shapes(self):
        assert parse_candidates({"visual_matches": ["not-a-dict", None]}) == []


class TestImageResolutionPreference:
    """Lens thumbnails are ~200px; after face-cropping to 112x112 that loses detail the
    embedding relies on. The full-size original must be preferred."""

    def test_prefers_original_over_thumbnail(self):
        got = parse_candidates({"visual_matches": [{
            "link": "https://instagram.com/p/A/",
            "original": "https://cdn/full.jpg",
            "thumbnail": "https://cdn/thumb.jpg",
        }]})
        assert got[0].image_url == "https://cdn/full.jpg"
        assert got[0].thumbnail_url == "https://cdn/thumb.jpg"

    def test_falls_back_to_thumbnail_when_no_original(self):
        got = parse_candidates({"visual_matches": [{
            "link": "https://instagram.com/p/A/", "thumbnail": "https://cdn/thumb.jpg",
        }]})
        assert got[0].image_url == "https://cdn/thumb.jpg"
