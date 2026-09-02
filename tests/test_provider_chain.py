"""Provider fallback chain.

Each provider is a different INDEX, not a better model. If Google's crawl does not contain the
subject, a better embedding cannot help -- another index can. The chain exists for that reason.

The property that must survive fallback: a provider FAILING is never the same as it searching and
finding nothing (HC-17). Fallback makes that easier to blur, so it is tested directly.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from facechain.config import Config
from facechain.errors import NoVerifiedMatchError, SearchProviderError
from facechain.providers import Providers, provider_by_name, resolve_chain
from facechain.search.lens import Candidate

FX = Path(__file__).parent / "fixtures"


class TestChainResolution:
    def test_default_order_is_lens_then_yandex_then_facecheck(self):
        assert [n for n, _ in resolve_chain(Config())] == [
            "google_lens", "yandex", "facecheck",
        ]

    def test_free_providers_precede_the_paid_one(self):
        names = [n for n, _ in resolve_chain(Config())]
        assert names.index("yandex") < names.index("facecheck")

    def test_explicit_provider_leads_the_chain(self):
        assert [n for n, _ in resolve_chain(Config(search_provider="yandex"))][0] == "yandex"

    def test_no_provider_appears_twice(self):
        names = [n for n, _ in resolve_chain(Config(search_provider="facecheck"))]
        assert len(names) == len(set(names))

    def test_fallback_can_be_disabled(self):
        chain = resolve_chain(Config(search_provider="yandex", provider_fallback=False))
        assert [n for n, _ in chain] == ["yandex"]

    @pytest.mark.parametrize("name,module", [
        ("yandex", "yandex"), ("facecheck", "facecheck"),
    ])
    def test_names_resolve_to_the_right_backend(self, name, module):
        assert module in provider_by_name(name).__module__

    def test_unknown_name_falls_back_to_lens(self):
        from facechain.providers import google_lens_search

        assert provider_by_name("nonsense") is google_lens_search


class TestFallbackBehaviour:
    """Driven through the real pipeline with substituted search functions."""

    @staticmethod
    def _providers(search_fn, image_bytes):
        base, calls = _fakes(image_bytes)
        return Providers(search_fn, base.image_upload, base.fetch_image), calls

    def test_all_providers_failing_raises_provider_error_not_no_match(self, tmp_path, monkeypatch):
        """We never searched. Reporting 'found nothing' would be a lie about what happened."""
        import facechain.pipeline as P

        def boom(image, cfg):
            raise SearchProviderError("down", {"status": 503})

        monkeypatch.setattr(P, "resolve_chain",
                            lambda cfg: [("a", boom), ("b", boom), ("c", boom)])
        cfg = Config(network="local", artifacts_dir=str(tmp_path))
        with pytest.raises(SearchProviderError) as e:
            P.run(FX / "faces_multi.jpg", cfg)
        assert "no search was actually performed" in str(e.value)

    def test_falls_through_to_a_later_provider(self, tmp_path, monkeypatch):
        import facechain.pipeline as P

        probe = (FX / "faces_multi.jpg").read_bytes()
        tried = []

        def empty(image, cfg):
            tried.append("first")
            return []

        def finds(image, cfg):
            tried.append("second")
            return [Candidate("https://www.instagram.com/p/X/", "https://cdn/a.jpg", "t", "s")]

        base, _ = _fakes(probe)
        monkeypatch.setattr(P, "resolve_chain",
                            lambda cfg: [("first", empty), ("second", finds)])
        monkeypatch.setattr(P, "default_providers", lambda cfg: base)

        cfg = Config(network="local", artifacts_dir=str(tmp_path), threshold=0.45)
        result = P.run(FX / "faces_multi.jpg", cfg)
        assert result.provider == "second"
        assert "first" in tried and "second" in tried

    def test_stops_at_the_first_provider_that_matches(self, tmp_path, monkeypatch):
        """A later provider must not be queried once a match is found -- it can cost money."""
        import facechain.pipeline as P

        probe = (FX / "faces_multi.jpg").read_bytes()
        later_called = []

        def finds(image, cfg):
            return [Candidate("https://www.instagram.com/p/X/", "https://cdn/a.jpg", "t", "s")]

        def later(image, cfg):
            later_called.append(True)
            return []

        base, _ = _fakes(probe)
        monkeypatch.setattr(P, "resolve_chain", lambda cfg: [("a", finds), ("paid", later)])
        monkeypatch.setattr(P, "default_providers", lambda cfg: base)
        P.run(FX / "faces_multi.jpg", Config(network="local", artifacts_dir=str(tmp_path)))
        assert later_called == [], "must not query a paid provider after a match"

    def test_one_provider_erroring_does_not_end_the_run(self, tmp_path, monkeypatch):
        import facechain.pipeline as P

        probe = (FX / "faces_multi.jpg").read_bytes()

        def broken(image, cfg):
            raise SearchProviderError("missing key")

        def works(image, cfg):
            return [Candidate("https://www.instagram.com/p/X/", "https://cdn/a.jpg", "t", "s")]

        base, _ = _fakes(probe)
        monkeypatch.setattr(P, "resolve_chain", lambda cfg: [("broken", broken), ("works", works)])
        monkeypatch.setattr(P, "default_providers", lambda cfg: base)
        result = P.run(FX / "faces_multi.jpg", Config(network="local", artifacts_dir=str(tmp_path)))
        assert result.provider == "works"
        assert result.attempts[0]["outcome"] == "provider_error"

    def test_attempts_record_every_provider_outcome(self, tmp_path, monkeypatch):
        import facechain.pipeline as P

        def empty(image, cfg):
            return []

        base, _ = _fakes((FX / "faces_multi.jpg").read_bytes())
        monkeypatch.setattr(P, "resolve_chain", lambda cfg: [("a", empty), ("b", empty)])
        monkeypatch.setattr(P, "default_providers", lambda cfg: base)
        with pytest.raises(NoVerifiedMatchError) as e:
            P.run(FX / "faces_multi.jpg", Config(network="local", artifacts_dir=str(tmp_path)))
        assert "a, b" in str(e.value)

    def test_explicit_providers_bypass_the_chain(self, tmp_path):
        """Injection must win: a supplied Providers is a choice, not a starting point."""
        import facechain.pipeline as P

        def finds(image, cfg):
            return [Candidate("https://www.instagram.com/p/X/", "https://cdn/a.jpg", "t", "s")]

        base, _ = _fakes((FX / "faces_multi.jpg").read_bytes())
        provs = Providers(finds, base.image_upload, base.fetch_image)
        result = P.run(FX / "faces_multi.jpg",
                       Config(network="local", artifacts_dir=str(tmp_path)), providers=provs)
        assert result.n_verified >= 1


def _fakes(image_bytes):
    from tests.fakes import make_fake_providers

    return make_fake_providers([], image_bytes=image_bytes)
