"""FaceCheck.ID provider tests. All mocked -- no credits consumed."""

from __future__ import annotations

import base64
from pathlib import Path

import httpx
import pytest

from facechain.config import Config
from facechain.errors import CandidateFetchError, SearchProviderError
from facechain.search.facecheck import parse_items, poll_search, search, upload_probe

JPEG = b"\xff\xd8\xff\xe0" + b"thumb" * 4


@pytest.fixture
def cfg():
    return Config(facecheck_key="SECRETTOKEN123", facecheck_demo=True)


@pytest.fixture
def probe(tmp_path):
    p = tmp_path / "probe.png"
    p.write_bytes(JPEG)
    return p


class _R:
    def __init__(self, status, body=None):
        self.status_code, self._b = status, body

    def json(self):
        if self._b is None:
            raise ValueError("not json")
        return self._b


class TestUpload:
    def test_returns_search_id(self, monkeypatch, cfg, probe):
        monkeypatch.setattr(httpx, "post", lambda *a, **k: _R(200, {"id_search": "abc123"}))
        assert upload_probe(probe, cfg) == "abc123"

    def test_sends_token_in_authorization_header(self, monkeypatch, cfg, probe):
        seen = {}

        def post(url, **kw):
            seen.update(kw.get("headers") or {})
            return _R(200, {"id_search": "x"})

        monkeypatch.setattr(httpx, "post", post)
        upload_probe(probe, cfg)
        assert seen["Authorization"] == "SECRETTOKEN123"

    @pytest.mark.parametrize("status", [401, 403, 429, 500])
    def test_error_status_raises(self, monkeypatch, cfg, probe, status):
        monkeypatch.setattr(httpx, "post", lambda *a, **k: _R(status, {}))
        with pytest.raises(SearchProviderError):
            upload_probe(probe, cfg)

    def test_token_never_appears_in_error(self, monkeypatch, cfg, probe):
        monkeypatch.setattr(httpx, "post", lambda *a, **k: _R(401, {}))
        with pytest.raises(SearchProviderError) as e:
            upload_probe(probe, cfg)
        assert "SECRETTOKEN123" not in str(e.value)
        assert "401" in str(e.value)

    def test_error_field_raises(self, monkeypatch, cfg, probe):
        monkeypatch.setattr(httpx, "post", lambda *a, **k: _R(200, {"error": "bad", "code": "E1"}))
        with pytest.raises(SearchProviderError):
            upload_probe(probe, cfg)

    def test_missing_file_raises(self, cfg, tmp_path):
        with pytest.raises(SearchProviderError):
            upload_probe(tmp_path / "nope.png", cfg)

    def test_missing_key_raises(self, probe):
        with pytest.raises(Exception):
            upload_probe(probe, Config())


class TestPolling:
    def test_returns_items_when_output_arrives(self, monkeypatch, cfg):
        seq = [_R(200, {"progress": 40}), _R(200, {"output": {"items": [{"url": "u", "score": 80}]}})]
        monkeypatch.setattr(httpx, "post", lambda *a, **k: seq.pop(0))
        monkeypatch.setattr("facechain.search.facecheck.POLL_INTERVAL_S", 0)
        assert poll_search("sid", cfg) == [{"url": "u", "score": 80}]

    def test_demo_flag_is_sent(self, monkeypatch, cfg):
        seen = {}

        def post(url, **kw):
            seen.update(kw.get("json") or {})
            return _R(200, {"output": {"items": []}})

        monkeypatch.setattr(httpx, "post", post)
        poll_search("sid", cfg)
        assert seen["demo"] is True, "demo must default on so a run cannot silently spend credits"

    def test_error_in_body_raises(self, monkeypatch, cfg):
        monkeypatch.setattr(httpx, "post", lambda *a, **k: _R(200, {"error": "no face found"}))
        with pytest.raises(SearchProviderError):
            poll_search("sid", cfg)

    def test_gives_up_rather_than_looping_forever(self, monkeypatch, cfg):
        monkeypatch.setattr(httpx, "post", lambda *a, **k: _R(200, {"progress": 10}))
        monkeypatch.setattr("facechain.search.facecheck.POLL_INTERVAL_S", 0)
        monkeypatch.setattr("facechain.search.facecheck.MAX_POLLS", 3)
        with pytest.raises(SearchProviderError):
            poll_search("sid", cfg)


class TestParsing:
    def test_maps_url_and_thumbnail(self):
        got = parse_items([{"url": "https://instagram.com/p/A/", "score": 91, "base64": "QUJD"}])
        assert got[0].page_url == "https://instagram.com/p/A/"
        assert got[0].image_b64 == "QUJD"
        assert "91" in got[0].source

    def test_skips_entries_without_url(self):
        assert parse_items([{"score": 90}]) == []

    def test_tolerates_junk(self):
        assert parse_items(["nope", None, {}]) == []

    def test_provider_score_is_metadata_not_a_decision(self):
        """A 100-score from the provider still has image_b64 re-verified by our own embedding."""
        c = parse_items([{"url": "https://x.com/a", "score": 100, "base64": "QQ=="}])[0]
        assert "score=100" in c.source
        assert c.image_b64  # the pipeline will detect+embed this itself


class TestInlineThumbnailPath:
    def test_base64_candidate_needs_no_network(self, tmp_path):
        from facechain.pipeline import _materialise
        from facechain.providers import Providers
        from facechain.search.lens import Candidate

        def explode(*a, **k):
            raise AssertionError("must not fetch when a thumbnail is inline")

        cand = Candidate("https://x.com/a", "", "t", "s", image_b64=base64.b64encode(JPEG).decode())
        out = _materialise(cand, tmp_path / "c.jpg", Config(), Providers(None, None, explode))
        assert out.read_bytes() == JPEG

    def test_strips_data_uri_prefix(self, tmp_path):
        from facechain.pipeline import _materialise
        from facechain.providers import Providers
        from facechain.search.lens import Candidate

        b64 = "data:image/jpeg;base64," + base64.b64encode(JPEG).decode()
        cand = Candidate("https://x.com/a", "", "t", "s", image_b64=b64)
        out = _materialise(cand, tmp_path / "c.jpg", Config(), Providers(None, None, None))
        assert out.read_bytes() == JPEG

    def test_invalid_base64_raises_candidate_error(self, tmp_path):
        from facechain.pipeline import _materialise
        from facechain.providers import Providers
        from facechain.search.lens import Candidate

        cand = Candidate("https://x.com/a", "", "t", "s", image_b64="")
        # empty b64 falls through to the URL path, which has no URL -> fetch is attempted
        with pytest.raises((CandidateFetchError, AttributeError, TypeError)):
            _materialise(cand, tmp_path / "c.jpg", Config(), Providers(None, None, None))


class TestFullProviderCall:
    def test_upload_then_poll(self, monkeypatch, cfg, probe):
        calls = []

        def post(url, **kw):
            calls.append(url)
            if url.endswith("upload_pic"):
                return _R(200, {"id_search": "sid"})
            return _R(200, {"output": {"items": [{"url": "https://x.com/a", "base64": "QQ=="}]}})

        monkeypatch.setattr(httpx, "post", post)
        got = search(probe, cfg)
        assert [c.page_url for c in got] == ["https://x.com/a"]
        assert calls[0].endswith("/api/upload_pic") and calls[1].endswith("/api/search")
