"""Typed configuration, constructed once at the CLI boundary.

This is the ONLY module in the project that reads ``os.environ`` (FR-054). Every other module
receives a frozen `Config` and never reaches for the environment itself, which is what lets tests
construct configuration directly without touching process state.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from typing import Literal

from .errors import FaceChainError

Network = Literal["local", "base-sepolia"]
SearchProvider = Literal["google_lens", "facecheck", "yandex"]

DEFAULT_SOCIAL_DOMAINS: tuple[str, ...] = (
    "instagram.com",
    "x.com",
    "twitter.com",
    "facebook.com",
    "linkedin.com",
    "tiktok.com",
    "threads.net",
    "reddit.com",
    "bsky.app",
    "youtube.com",
)

# Portfolio, professional and creative platforms where people keep public profiles. Kept separate
# from DEFAULT_SOCIAL_DOMAINS because the task speaks of "social media posts", and the distinction
# is worth preserving in the evidence rather than blurring. Both sets are searched: a Yandex query
# for a face returns Behance, ResearchGate and Xing profiles far more often than Instagram, and
# dropping them threw away most of what that provider is good at finding.
DEFAULT_PROFILE_DOMAINS: tuple[str, ...] = (
    "behance.net", "dribbble.com", "researchgate.net", "xing.com", "fiverr.com",
    "upwork.com", "github.com", "gitlab.com", "medium.com", "substack.com",
    "about.me", "devfolio.co", "devpost.com", "kaggle.com", "orcid.org",
    "academia.edu", "stackoverflow.com", "producthunt.com", "wellfound.com",
    "twitch.tv", "vimeo.com", "flickr.com", "soundcloud.com", "imdb.com",
    "goodreads.com", "pinterest.com", "thoughtleaders.io",
)

# Portfolio, professional and creative platforms where people keep public profiles. Kept separate
# from DEFAULT_SOCIAL_DOMAINS because the task speaks of "social media posts", and the distinction
# is worth preserving in the evidence rather than blurring. Both sets are searched: a Yandex query
# for a face returns Behance, ResearchGate and Xing profiles far more often than Instagram, and
# dropping them threw away most of what that provider is good at finding.
DEFAULT_PROFILE_DOMAINS: tuple[str, ...] = (
    "behance.net", "dribbble.com", "researchgate.net", "xing.com", "fiverr.com",
    "upwork.com", "github.com", "gitlab.com", "medium.com", "substack.com",
    "about.me", "devfolio.co", "devpost.com", "kaggle.com", "orcid.org",
    "academia.edu", "stackoverflow.com", "producthunt.com", "wellfound.com",
    "twitch.tv", "vimeo.com", "flickr.com", "soundcloud.com", "imdb.com",
    "goodreads.com", "pinterest.com", "thoughtleaders.io",
)

DEFAULT_RPC_URLS: dict[str, str] = {"base-sepolia": "https://sepolia.base.org"}


class _Secret(str):
    """A string whose repr is redacted, so a Config is always safe to log."""

    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return "'<redacted>'"


@dataclass(frozen=True)
class Config:
    network: Network = "local"
    rpc_url: str | None = None
    private_key: str | None = None
    contract_address: str | None = None
    serpapi_key: str | None = None
    imgbb_key: str | None = None
    facecheck_key: str | None = None
    # demo mode scans a reduced index and consumes no credits -- the default, so a misconfigured
    # run cannot silently spend money
    facecheck_demo: bool = True
    search_provider: SearchProvider = "google_lens"
    threshold: float = 0.45
    social_domains: tuple[str, ...] = DEFAULT_SOCIAL_DOMAINS
    profile_domains: tuple[str, ...] = DEFAULT_PROFILE_DOMAINS
    max_candidates: int = 20
    fetch_timeout_s: float = 10.0
    max_image_bytes: int = 8 * 1024 * 1024
    fetch_concurrency: int = 4
    artifacts_dir: str = "artifacts"

    def require(self, *names: str) -> None:
        """Raise if any named field is unset.

        Called at the boundary that actually needs the value, so a missing SerpAPI key never
        blocks an offline ``verify`` that has no use for it.
        """
        missing = [n for n in names if not getattr(self, n, None)]
        if missing:
            raise FaceChainError(
                f"missing required configuration: {', '.join(missing)}",
                {"hint": "set them in .env (see .env.example)"},
            )

    def with_overrides(self, **kwargs: object) -> Config:
        return replace(self, **{k: v for k, v in kwargs.items() if v is not None})


def _secret(value: str | None) -> str | None:
    return _Secret(value) if value else None


def load_config(**overrides: object) -> Config:
    """Build a Config from the environment, then apply non-None overrides.

    Overrides beat the environment so CLI flags always win.
    """
    network = str(overrides.pop("network", None) or os.environ.get("NETWORK") or "local")
    if network not in ("local", "base-sepolia"):
        raise FaceChainError(
            f"unknown network: {network!r}", {"valid": "local, base-sepolia"}
        )

    cfg = Config(
        network=network,  # type: ignore[arg-type]
        rpc_url=os.environ.get("RPC_URL") or DEFAULT_RPC_URLS.get(network),
        private_key=_secret(os.environ.get("PRIVATE_KEY")),
        contract_address=os.environ.get("CONTRACT_ADDRESS"),
        serpapi_key=_secret(os.environ.get("SERPAPI_KEY")),
        imgbb_key=_secret(os.environ.get("IMGBB_KEY")),
        facecheck_key=_secret(os.environ.get("FACECHECK_KEY")),
        facecheck_demo=os.environ.get("FACECHECK_DEMO", "1") not in ("0", "false", "False"),
        search_provider=str(
            overrides.pop("search_provider", None)
            or os.environ.get("SEARCH_PROVIDER")
            or "google_lens"
        ),  # type: ignore[arg-type]
    )
    return cfg.with_overrides(**overrides)
