"""Candidate filtering: social-domain allowlist, URL normalisation, de-duplication."""

from __future__ import annotations

import re
from urllib.parse import urlsplit, urlunsplit

from ..config import Config
from .lens import Candidate

# A Mastodon-style instance exposes posts at /@handle/... on an arbitrary domain.
MASTODON_PATH = re.compile(r"/@[A-Za-z0-9_]+")


def normalise_url(url: str) -> str:
    """Canonical form for de-duplication: drop query, fragment, and trailing slash."""
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return url.strip().lower()
    host = (parts.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    path = (parts.path or "").rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower() or "https", host, path, "", ""))


def registrable_host(url: str) -> str:
    try:
        host = (urlsplit(url).netloc or "").lower()
    except ValueError:
        return ""
    return host[4:] if host.startswith("www.") else host


def is_core_social(url: str, cfg: Config) -> bool:
    """True only for the strict social-media set, not portfolio/profile platforms.

    A Devfolio or GitHub hit can be a genuine face match while every Instagram/LinkedIn
    *image* the search returned is a different person. Those are different outcomes.
    """
    host = registrable_host(url)
    if not host:
        return False
    for domain in cfg.social_domains:
        if host == domain or host.endswith("." + domain):
            return True
    return False


def is_social(url: str, cfg: Config) -> bool:
    """True for a page where a person plausibly has a public presence.

    Covers both the strict social set and the professional/portfolio set: a face search returns
    Behance, ResearchGate and Xing profiles far more often than Instagram posts, and excluding
    them discarded most of what the Yandex provider finds.

    Matches on the registrable domain, never a substring -- a substring check would admit
    `notinstagram.com.evil.co`.
    """
    host = registrable_host(url)
    if not host:
        return False
    for domain in tuple(cfg.social_domains) + tuple(cfg.profile_domains):
        if host == domain or host.endswith("." + domain):
            return True
    try:
        if MASTODON_PATH.search(urlsplit(url).path or ""):
            return True
    except ValueError:
        pass
    return False


def filter_social(cands: list[Candidate], cfg: Config) -> list[Candidate]:
    """Keep social-media candidates, de-duplicated, in first-seen order."""
    seen: set[str] = set()
    out: list[Candidate] = []
    for c in cands:
        if not is_social(c.page_url, cfg):
            continue
        key = normalise_url(c.page_url)
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
        if len(out) >= cfg.max_candidates:
            break
    return out


def union(*groups: list[Candidate]) -> list[Candidate]:
    """Order-stable union across candidate groups; first occurrence wins."""
    seen: set[str] = set()
    out: list[Candidate] = []
    for group in groups:
        for c in group:
            key = normalise_url(c.page_url)
            if key not in seen:
                seen.add(key)
                out.append(c)
    return out
