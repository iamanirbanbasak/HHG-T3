from __future__ import annotations

import pytest

from facechain.config import Config, load_config
from facechain.errors import FaceChainError


class TestSecretRedaction:
    """A Config must be safe to log. NFR-011."""

    @pytest.mark.parametrize("field", ["private_key", "serpapi_key", "imgbb_key"])
    def test_secret_absent_from_repr(self, monkeypatch, field):
        env = {"private_key": "PRIVATE_KEY", "serpapi_key": "SERPAPI_KEY", "imgbb_key": "IMGBB_KEY"}
        monkeypatch.setenv(env[field], "SUPERSECRETVALUE123")
        cfg = load_config()
        assert "SUPERSECRETVALUE123" not in repr(cfg)
        assert "SUPERSECRETVALUE123" not in str(cfg)
        assert getattr(cfg, field) == "SUPERSECRETVALUE123"  # still usable

    def test_all_secrets_redacted_together(self, monkeypatch):
        for k in ("PRIVATE_KEY", "SERPAPI_KEY", "IMGBB_KEY"):
            monkeypatch.setenv(k, f"secret-{k}")
        r = repr(load_config())
        assert "secret-" not in r


class TestOverrides:
    def test_overrides_beat_environment(self, monkeypatch):
        monkeypatch.setenv("NETWORK", "base-sepolia")
        assert load_config(network="local").network == "local"

    def test_none_override_does_not_clobber(self):
        assert Config(threshold=0.6).with_overrides(threshold=None).threshold == 0.6

    def test_unknown_network_raises(self):
        with pytest.raises(FaceChainError):
            load_config(network="mainnet")


class TestRequire:
    def test_missing_required_field_raises_typed_error(self):
        with pytest.raises(FaceChainError) as e:
            Config().require("serpapi_key")
        assert "serpapi_key" in str(e.value)

    def test_present_field_passes(self):
        Config(serpapi_key="x").require("serpapi_key")

    def test_unused_missing_key_is_not_an_error(self):
        """An offline verify must not demand a SerpAPI key it never uses."""
        Config(contract_address="0xabc").require("contract_address")


def test_defaults():
    c = Config()
    assert c.threshold == 0.45
    assert c.network == "local"
    assert c.fetch_concurrency == 4
    assert "instagram.com" in c.social_domains
