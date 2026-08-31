"""Candidate retrieval security: SSRF, size caps, content sniffing."""

from __future__ import annotations

import httpx
import pytest

from facechain.config import Config
from facechain.errors import CandidateFetchError
from facechain.search.fetch import assert_safe_url, fetch_image, looks_like_image

JPEG = b"\xff\xd8\xff\xe0" + b"padding"


class TestSsrf:
    @pytest.mark.parametrize("url", [
        "http://example.com/i.jpg", "file:///etc/passwd", "data:image/png;base64,AA",
        "ftp://example.com/i.jpg",
    ])
    def test_non_https_rejected(self, url):
        with pytest.raises(CandidateFetchError):
            assert_safe_url(url)

    @pytest.mark.parametrize("url", [
        "https://localhost/i.jpg", "https://127.0.0.1/i.jpg", "https://[::1]/i.jpg",
    ])
    def test_internal_addresses_rejected(self, url):
        with pytest.raises(CandidateFetchError):
            assert_safe_url(url)

    def test_missing_host_rejected(self):
        with pytest.raises(CandidateFetchError):
            assert_safe_url("https:///i.jpg")


class TestContentSniffing:
    def test_recognises_real_image_magic(self):
        assert looks_like_image(b"\xff\xd8\xff")
        assert looks_like_image(b"\x89PNG\r\n\x1a\n")

    def test_rejects_html_masquerading_as_image(self):
        assert not looks_like_image(b"<!DOCTYPE html>")


class _Stream:
    def __init__(self, status, chunks):
        self.status_code, self._chunks = status, chunks

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def iter_bytes(self, n=None):
        yield from self._chunks


class TestFetch:
    def test_size_cap_enforced_during_streaming(self, monkeypatch, tmp_path):
        """The cap must abort mid-download, not after buffering the whole response."""
        cfg = Config(max_image_bytes=1000)
        big = [b"\xff\xd8\xff" + b"x" * 900, b"y" * 900, b"z" * 900]
        monkeypatch.setattr("facechain.search.fetch.assert_safe_url", lambda u: None)
        monkeypatch.setattr(httpx, "stream", lambda *a, **k: _Stream(200, big))
        with pytest.raises(CandidateFetchError) as e:
            fetch_image("https://cdn.test/i.jpg", tmp_path / "o.jpg", cfg)
        assert "size cap" in str(e.value)

    def test_non_200_raises(self, monkeypatch, tmp_path):
        monkeypatch.setattr("facechain.search.fetch.assert_safe_url", lambda u: None)
        monkeypatch.setattr(httpx, "stream", lambda *a, **k: _Stream(403, []))
        with pytest.raises(CandidateFetchError):
            fetch_image("https://cdn.test/i.jpg", tmp_path / "o.jpg", Config())

    def test_non_image_body_raises(self, monkeypatch, tmp_path):
        monkeypatch.setattr("facechain.search.fetch.assert_safe_url", lambda u: None)
        monkeypatch.setattr(httpx, "stream", lambda *a, **k: _Stream(200, [b"<html>"]))
        with pytest.raises(CandidateFetchError):
            fetch_image("https://cdn.test/i.jpg", tmp_path / "o.jpg", Config())

    def test_successful_fetch_writes_file(self, monkeypatch, tmp_path):
        monkeypatch.setattr("facechain.search.fetch.assert_safe_url", lambda u: None)
        monkeypatch.setattr(httpx, "stream", lambda *a, **k: _Stream(200, [JPEG]))
        out = fetch_image("https://cdn.test/i.jpg", tmp_path / "o.jpg", Config())
        assert out.read_bytes() == JPEG

    def test_timeout_raises_typed_error(self, monkeypatch, tmp_path):
        def boom(*a, **k):
            raise httpx.TimeoutException("slow")

        monkeypatch.setattr("facechain.search.fetch.assert_safe_url", lambda u: None)
        monkeypatch.setattr(httpx, "stream", boom)
        with pytest.raises(CandidateFetchError):
            fetch_image("https://cdn.test/i.jpg", tmp_path / "o.jpg", Config())
