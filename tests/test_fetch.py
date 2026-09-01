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


@pytest.fixture
def mock_http(monkeypatch):
    """Route fetch_image through real httpx machinery with a fake transport.

    Deliberately NOT a monkeypatch of httpx.stream: mocking the call itself hid a real bug
    (max_redirects is not a valid argument there). Here the genuine Client is constructed with
    the real kwargs, so a signature error surfaces.
    """

    def install(handler):
        transport = httpx.MockTransport(handler)
        original = httpx.Client

        def factory(*args, **kwargs):
            kwargs["transport"] = transport
            return original(*args, **kwargs)

        monkeypatch.setattr(httpx, "Client", factory)
        monkeypatch.setattr("facechain.search.fetch.assert_safe_url", lambda u: None)

    return install


class TestFetch:
    def test_size_cap_enforced_during_streaming(self, mock_http, tmp_path):
        """The cap must abort mid-download, not after buffering the whole response."""
        body = b"\xff\xd8\xff" + b"x" * 5000
        mock_http(lambda req: httpx.Response(200, content=body))
        with pytest.raises(CandidateFetchError) as e:
            fetch_image("https://cdn.example.com/i.jpg", tmp_path / "o.jpg",
                        Config(max_image_bytes=1000))
        assert "size cap" in str(e.value)

    def test_non_200_raises(self, mock_http, tmp_path):
        mock_http(lambda req: httpx.Response(403))
        with pytest.raises(CandidateFetchError):
            fetch_image("https://cdn.example.com/i.jpg", tmp_path / "o.jpg", Config())

    def test_non_image_body_raises(self, mock_http, tmp_path):
        mock_http(lambda req: httpx.Response(200, content=b"<!DOCTYPE html><html>"))
        with pytest.raises(CandidateFetchError):
            fetch_image("https://cdn.example.com/i.jpg", tmp_path / "o.jpg", Config())

    def test_successful_fetch_writes_file(self, mock_http, tmp_path):
        mock_http(lambda req: httpx.Response(200, content=JPEG))
        out = fetch_image("https://cdn.example.com/i.jpg", tmp_path / "o.jpg", Config())
        assert out.read_bytes() == JPEG

    def test_sends_browser_user_agent(self, mock_http, tmp_path):
        seen = {}

        def handler(req):
            seen["ua"] = req.headers.get("user-agent", "")
            return httpx.Response(200, content=JPEG)

        mock_http(handler)
        fetch_image("https://cdn.example.com/i.jpg", tmp_path / "o.jpg", Config())
        assert "Mozilla" in seen["ua"]

    def test_timeout_raises_typed_error(self, mock_http, tmp_path):
        def handler(req):
            raise httpx.TimeoutException("slow")

        mock_http(handler)
        with pytest.raises(CandidateFetchError):
            fetch_image("https://cdn.example.com/i.jpg", tmp_path / "o.jpg", Config())


class TestRealHttpxCompatibility:
    """Guards against mock-hidden signature errors.

    The unit tests above monkeypatch httpx, so they cannot detect that an argument does not exist
    on the real API. This was a live bug: `max_redirects` was passed to httpx.stream(), which
    accepts no such argument, and every candidate fetch failed in production while the mocked
    tests stayed green.
    """

    def test_client_accepts_the_arguments_fetch_image_uses(self):
        import httpx

        from facechain.config import Config

        cfg = Config()
        # Constructing is enough: a bad kwarg raises TypeError here, not at request time.
        with httpx.Client(
            timeout=cfg.fetch_timeout_s, follow_redirects=True, max_redirects=3
        ) as client:
            assert client is not None

    def test_stream_signature_rejects_max_redirects(self):
        """Documents WHY the client is constructed explicitly."""
        import inspect

        import httpx

        assert "max_redirects" not in inspect.signature(httpx.stream).parameters
        assert "max_redirects" in inspect.signature(httpx.Client.__init__).parameters

