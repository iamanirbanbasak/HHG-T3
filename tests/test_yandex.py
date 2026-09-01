"""Yandex provider tests.

Parsing is tested against a real captured results page, so a Yandex markup change breaks the test
rather than silently returning nothing in production. Network access is never required.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from facechain.config import Config
from facechain.errors import SearchProviderError
from facechain.search.yandex import (
    build_query_url,
    clean_url,
    is_bot_challenged,
    parse_results,
    search,
)

FIXTURE = Path(__file__).parent / "fixtures" / "yandex_sites.html"


class TestQueryUrl:
    def test_requests_the_sites_page_not_similar(self):
        """`similar` returns look-alike images with no page links, which is useless here."""
        url = build_query_url("https://i.ibb.co/x.png")
        assert "cbir_page=sites" in url and "rpt=imageview" in url

    def test_image_url_is_encoded(self):
        assert "https%3A%2F%2Fi.ibb.co%2Fx.png" in build_query_url("https://i.ibb.co/x.png")


class TestCleanUrl:
    def test_strips_yandex_tracking_params(self):
        got = clean_url("https://www.behance.net/user?utm_medium=organic&utm_source=yandexsmartcamera")
        assert got == "https://www.behance.net/user"

    def test_keeps_meaningful_query_params(self):
        got = clean_url("https://x.com/a?id=7&utm_source=yandexsmartcamera")
        assert "id=7" in got and "utm_source" not in got

    def test_leaves_clean_urls_alone(self):
        assert clean_url("https://x.com/a") == "https://x.com/a"

    def test_tolerates_malformed_input(self):
        assert clean_url("not a url") == "not a url"


class TestParsing:
    @pytest.fixture(scope="class")
    def results(self):
        return parse_results(FIXTURE.read_text())

    def test_extracts_candidates_from_a_real_page(self, results):
        assert len(results) >= 10

    def test_page_urls_are_real_pages_not_yandex(self, results):
        assert all(c.page_url.startswith("http") for c in results)
        assert not any("yandex.com/images" in c.page_url for c in results)

    def test_tracking_params_are_stripped(self, results):
        assert not any("utm_source=yandexsmartcamera" in c.page_url for c in results)

    def test_titles_are_captured(self, results):
        assert sum(1 for c in results if c.title.strip()) >= 8

    def test_source_names_the_provider(self, results):
        assert all(c.source.startswith("yandex") for c in results)

    def test_finds_people_pages_not_product_listings(self, results):
        """The reason this provider exists: Lens returned garment listings for the same probe."""
        hosts = " ".join(c.page_url for c in results)
        assert any(d in hosts for d in ("behance.net", "researchgate.net", "youtube.com", "xing.com"))

    def test_empty_html_yields_no_candidates(self):
        assert parse_results("<html><body></body></html>") == []

    def test_malformed_html_does_not_raise(self):
        assert parse_results("<div class='CbirSites-Item'><a>no href</a></div>") == []


class TestBotChallenge:
    @pytest.mark.parametrize("body", [
        "<html>showcaptcha</html>",
        "<html>Are you a robot?</html>",
        "<html>Confirm you are not a robot</html>",
    ])
    def test_detects_challenge_pages(self, body):
        assert is_bot_challenged(body)

    def test_clean_page_is_not_flagged(self):
        assert not is_bot_challenged(FIXTURE.read_text())

    def test_challenge_raises_rather_than_returning_empty(self, monkeypatch, tmp_path):
        """A blocked scrape must never look like a genuine 'found nothing'."""
        class FakePage:
            status = 200
            html_content = "<html>showcaptcha</html>"

        import facechain.search.yandex as Y

        monkeypatch.setattr(Y, "upload", lambda p, c: "https://host/x.png", raising=False)
        import scrapling.fetchers as F

        monkeypatch.setattr(F.StealthyFetcher, "fetch", staticmethod(lambda *a, **k: FakePage()))
        with pytest.raises(SearchProviderError) as e:
            search(tmp_path / "x.png", Config(imgbb_key="k"), hosted_url="https://host/x.png")
        assert "bot challenge" in str(e.value)


class TestErrorHandling:
    def test_non_200_raises(self, monkeypatch, tmp_path):
        class FakePage:
            status = 503
            html_content = ""

        import scrapling.fetchers as F

        monkeypatch.setattr(F.StealthyFetcher, "fetch", staticmethod(lambda *a, **k: FakePage()))
        with pytest.raises(SearchProviderError):
            search(tmp_path / "x.png", Config(), hosted_url="https://host/x.png")

    def test_fetch_exception_becomes_provider_error(self, monkeypatch, tmp_path):
        def boom(*a, **k):
            raise RuntimeError("browser crashed")

        import scrapling.fetchers as F

        monkeypatch.setattr(F.StealthyFetcher, "fetch", staticmethod(boom))
        with pytest.raises(SearchProviderError):
            search(tmp_path / "x.png", Config(), hosted_url="https://host/x.png")


def test_provider_is_selectable_by_config():
    from facechain.providers import default_providers
    from facechain.search.yandex import search as yandex_search

    assert default_providers(Config(search_provider="yandex")).face_search is yandex_search
