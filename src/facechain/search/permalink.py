"""Resolve a post permalink to the account that published it.

Instagram `/p/{shortcode}/` URLs do not contain a handle. Guessing one from the shortcode
would invent an identity next to a real cosine score. This module only accepts a handle that
the search provider already returned in title/source, that Google reports for that same post,
or that oEmbed / owner JSON names. It never scrapes arbitrary `instagram.com/...` paths out
of HTML -- those are static assets (`rsrc.php`) and login URLs, not accounts.
"""

from __future__ import annotations

import json
import re
from urllib.parse import quote

from ..config import Config
from ..profiles import handle_of, platform_of
from .lens import Candidate

_RESERVED = {
    "instagram", "photo", "video", "reel", "reels", "post", "posts", "official",
    "explore", "stories", "highlight", "watch", "tv", "live", "accounts", "login",
    "rsrc", "static", "ajax", "graphql", "media", "about", "privacy", "help",
    "legal", "challenge", "session", "developer", "directory", "emails", "api",
    "www", "index", "anonymous", "guest", "none", "null", "embed", "captioned",
}

_TITLE = [
    re.compile(r"(?:photo|video|reel|post)\s+by\s+@?([A-Za-z0-9._]{2,30})\b", re.I),
    re.compile(r"^@?([A-Za-z0-9._]{2,30})\s+on\s+instagram\b", re.I | re.M),
    re.compile(r"instagram\s+post\s+from\s+@?([A-Za-z0-9._]{2,30})\b", re.I),
    # SerpAPI `source` when the result title is the caption, not the username:
    # "Instagram · jane.doe" (the separator may be any punctuation, including unicode dots)
    re.compile(
        r"^instagram\s+[^\w\s]\s*@?([A-Za-z0-9._]{2,30})\s*$",
        re.I | re.M,
    ),
    # Google breadcrumb: instagram.com › jane.doe
    re.compile(r"instagram\.com\s*[›>/]\s*@?([A-Za-z0-9._]{2,30})\b", re.I),
]
_OWNER_JSON = re.compile(
    r'"owner"\s*:\s*\{[^{}]{0,500}?"username"\s*:\s*"([A-Za-z0-9._]{2,30})"',
    re.I,
)
_AUTHOR_JSON = re.compile(r'"author_name"\s*:\s*"([A-Za-z0-9._]{2,30})"')
_HANDLE = re.compile(r"^[A-Za-z0-9._]{2,30}$")
_FILE = re.compile(r"\.(php|js|css|html?|jpe?g|png|gif|webp|svg|json|map)$", re.I)


def resolve_owner(cand: Candidate, fetch_page, cfg: Config) -> str | None:
    """Return the publisher's handle, or None when it cannot be read honestly."""
    h = handle_of(cand.page_url)
    if h:
        return h
    h = handle_from_text(f"{cand.title}\n{cand.source}")
    if h:
        return h
    if platform_of(cand.page_url) != "instagram":
        return None
    from .websearch import search_post_owner

    h = search_post_owner(cand.page_url, cfg)
    if h:
        return h
    if fetch_page is None:
        return None
    h = _from_oembed(cand.page_url, fetch_page, cfg)
    if h:
        return h
    try:
        html = fetch_page(cand.page_url, cfg)
    except Exception:  # noqa: BLE001 - permalink resolution must not abort a run
        return None
    return handle_from_html(html)


def handle_from_text(text: str) -> str | None:
    """A handle the provider already printed, not one derived from the shortcode."""
    blob = (text or "").strip()
    if not blob:
        return None
    for pat in _TITLE:
        m = pat.search(blob)
        if m:
            h = _clean(m.group(1))
            if h:
                return h
    return None


def handle_from_html(html: str) -> str | None:
    """Owner JSON only. Never scan hrefs -- login-wall HTML is full of asset paths."""
    if not html:
        return None
    m = _OWNER_JSON.search(html) or _AUTHOR_JSON.search(html)
    if not m:
        return None
    return _clean(m.group(1))


def _from_oembed(page_url: str, fetch_page, cfg: Config) -> str | None:
    oembed = "https://www.instagram.com" + "/api/oembed/" + "?url=" + quote(page_url, safe="")
    try:
        raw = fetch_page(oembed, cfg)
    except Exception:  # noqa: BLE001
        return None
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    h = _clean(str(data.get("author_name") or ""))
    if h:
        return h
    return handle_of(str(data.get("author_url") or ""))


def _clean(raw: str) -> str | None:
    h = (raw or "").strip().lstrip("@")
    if not _HANDLE.match(h):
        return None
    if h.lower() in _RESERVED:
        return None
    if _FILE.search(h):
        return None
    return h
