"""Social links published on a face-verified page.

Reverse-image search often verifies a portfolio (Devfolio, Behance) while every LinkedIn /
GitHub / Facebook *image* it also returned is a different person and fails the cosine check.
Those failed candidates are not that person's accounts. The accounts they *do* claim are
usually listed on the page that did pass.

Links extracted here are claims on a face-verified page. They are not independently
face-scored, and they must never be presented as if they were.
"""

from __future__ import annotations

import re
from html import unescape
from urllib.parse import urljoin, urlsplit

from ..config import Config
from .candidates import is_social, normalise_url, registrable_host

ABS_URL = re.compile(r"https://[^\s\"'<>\\]+", re.I)
HREF = re.compile(r"""href\s*=\s*["']([^"']+)["']""", re.I)
OG_IMAGE = re.compile(
    r'<meta[^>]+(?:property|name)=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
    re.I,
)
OG_IMAGE_REV = re.compile(
    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']og:image["\']',
    re.I,
)

# Link-in-bio aggregators: not accounts themselves; we follow one hop to read the socials.
BIO_HUBS = (
    "linktr.ee", "beacons.ai", "bio.link", "lnk.bio", "carrd.co",
    "solo.to", "heylink.me", "allmylinks.com",
)

# Path/query shapes that are share buttons, auth, or embeds -- not a person's profile.
_NOISE = (
    "/intent/", "/share", "/sharer", "/login", "/signup", "/oauth",
    "/hashtag/", "/watch", "/embed/", "/groups/", "/pub/dir",
    "/dialog/", "/plugins/", "/i/flow",
)


def extract_profile_links(html: str, page_url: str, cfg: Config) -> list[str]:
    """Return allowlisted social/profile URLs found on `page_url`, first-seen order.

    Same-site links are dropped: a Devfolio page linking to other Devfolio URLs is not a
    new account. File assets (css, svg, avatars) are dropped too.
    """
    source_root = _allowlisted_root(registrable_host(page_url), cfg)
    seen: set[str] = set()
    out: list[str] = []

    raw_urls: list[str] = []
    for m in HREF.finditer(html):
        raw_urls.append(unescape(m.group(1).strip()))
    for m in ABS_URL.finditer(html):
        raw_urls.append(unescape(m.group(0).rstrip(".,);}]'\"")))

    for raw in raw_urls:
        if not raw or raw.startswith(("#", "javascript:", "mailto:", "tel:", "data:")):
            continue
        try:
            url = urljoin(page_url, raw)
        except ValueError:
            continue
        if not url.startswith("https://"):
            continue
        if not is_social(url, cfg):
            continue
        if _allowlisted_root(registrable_host(url), cfg) == source_root:
            continue
        if _is_noise(url) or _is_asset(url):
            continue
        key = normalise_url(url)
        if key in seen:
            continue
        seen.add(key)
        out.append(url)
    return out


def extract_hub_links(html: str, page_url: str) -> list[str]:
    """Link-in-bio pages found on `page_url` (at most a handful, first-seen)."""
    seen: set[str] = set()
    out: list[str] = []
    raw_urls: list[str] = []
    for m in HREF.finditer(html):
        raw_urls.append(unescape(m.group(1).strip()))
    for m in ABS_URL.finditer(html):
        raw_urls.append(unescape(m.group(0).rstrip(".,);}]'\"")))
    for raw in raw_urls:
        try:
            url = urljoin(page_url, raw)
        except ValueError:
            continue
        if not url.startswith("https://"):
            continue
        host = registrable_host(url)
        if not any(host == h or host.endswith("." + h) for h in BIO_HUBS):
            continue
        key = normalise_url(url)
        if key in seen:
            continue
        seen.add(key)
        out.append(url)
        if len(out) >= 2:
            break
    return out


def og_image(html: str, page_url: str) -> str:
    """The Open Graph image URL, or empty if the page does not declare one."""
    m = OG_IMAGE.search(html) or OG_IMAGE_REV.search(html)
    if not m:
        return ""
    try:
        url = urljoin(page_url, unescape(m.group(1).strip()))
    except ValueError:
        return ""
    return url if url.startswith("https://") else ""


def profile_guesses(handle: str, skip_platform: str) -> list[tuple[str, str, str]]:
    """Other-platform profile URLs for a verified handle.

    The third item is a direct avatar URL when the platform publishes one; otherwise the
    caller fetches the page and reads og:image. Same handle on two sites is a hypothesis,
    never a match -- the embedding still has to admit it.
    """
    h = handle.strip().lstrip("@")
    if not h:
        return []
    out: list[tuple[str, str, str]] = []
    github_ok = bool(re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9\-]{0,37}[A-Za-z0-9])?", h))
    templates = [
        ("github", f"https://github.com/{h}", f"https://github.com/{h}.png" if github_ok else ""),
        ("gitlab", f"https://gitlab.com/{h}", ""),
        ("youtube", f"https://www.youtube.com/@{h}", ""),
        ("reddit", f"https://www.reddit.com/user/{h}", ""),
        ("soundcloud", f"https://soundcloud.com/{h}", ""),
    ]
    for platform, page, avatar in templates:
        if platform == skip_platform:
            continue
        if platform == "github" and not github_ok:
            continue
        out.append((platform, page, avatar))
    return out


def _allowlisted_root(host: str, cfg: Config) -> str:
    """The allowlisted domain a host belongs to, e.g. acehack.devfolio.co -> devfolio.co."""
    if not host:
        return ""
    for domain in tuple(cfg.social_domains) + tuple(cfg.profile_domains):
        if host == domain or host.endswith("." + domain):
            return domain
    return host


_ASSET_SUFFIX = (
    ".css", ".js", ".svg", ".png", ".jpg", ".jpeg", ".webp", ".gif",
    ".ico", ".woff", ".woff2", ".map",
)


def _is_asset(url: str) -> bool:
    try:
        path = (urlsplit(url).path or "").lower()
    except ValueError:
        return True
    return path.endswith(_ASSET_SUFFIX)


def _is_noise(url: str) -> bool:
    try:
        parts = urlsplit(url)
    except ValueError:
        return True
    path = (parts.path or "").lower()
    if path in ("", "/"):
        return True
    blob = path + "?" + (parts.query or "").lower()
    return any(n in blob for n in _NOISE)
