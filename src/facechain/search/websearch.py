"""Google web search used to find LinkedIn profiles for a verified handle.

LinkedIn vanity URLs are not `{handle}` the way GitHub is, so a same-handle guess is not
enough. This runs a real `site:` query through SerpAPI (already required for Lens) and
returns profile URLs. Face verification still decides whether any of them are the same person.

Best-effort enrichment: a failed search returns [] and is logged. It must not turn a
successful face-match run into a provider error.
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit

import httpx

from ..config import Config
from .candidates import registrable_host
from .lens import ENDPOINT, Candidate

IN_PATH = re.compile(r"^/in/([A-Za-z0-9\-_%]{3,120})/?$", re.I)
SHORTCODE = re.compile(r"/(?:p|reel|reels)/([A-Za-z0-9_-]+)", re.I)
MAX_RESULTS = 3


def _google(q: str, cfg: Config) -> dict:
    if not q or not cfg.serpapi_key:
        return {}
    params = {
        "engine": "google",
        "q": q,
        "api_key": str(cfg.serpapi_key),
        "hl": "en",
        "num": 8,
    }
    try:
        resp = httpx.get(ENDPOINT, params=params, timeout=cfg.fetch_timeout_s * 3)
    except (httpx.TimeoutException, httpx.HTTPError):
        return {}
    if resp.status_code != 200:
        return {}
    try:
        body = resp.json()
    except ValueError:
        return {}
    if not isinstance(body, dict) or "error" in body:
        return {}
    return body


def search_linkedin(handle: str, cfg: Config) -> list[Candidate]:
    """Search for LinkedIn /in/ profiles matching `handle`."""
    h = handle.strip().lstrip("@")
    if not h:
        return []
    return parse_linkedin_results(_google(f'site:linkedin.com/in "{h}"', cfg))[:MAX_RESULTS]


def search_post_owner(page_url: str, cfg: Config) -> str | None:
    """Publisher of an Instagram post, taken from Google's hit for that same URL.

    Instagram's public HTML is a login shell and does not name the owner. Google
    often puts the username in the result title (`username on Instagram: ...`).
    When the title is only the caption, the handle still shows up as
    `source: "Instagram · username"`.
    """
    return owner_from_search(_google(page_url, cfg), page_url)


def owner_from_search(body: dict, page_url: str) -> str | None:
    from .permalink import handle_from_text

    code = _shortcode(page_url)
    if not code:
        return None
    for item in body.get("organic_results") or []:
        if not isinstance(item, dict):
            continue
        if _shortcode(item.get("link") or "") != code:
            continue
        # Title is preferred, but for caption-titled posts the publisher is in
        # `source` (and sometimes the displayed breadcrumb). Snippets are ignored:
        # a caption can @mention someone who is not the owner.
        blob = "\n".join(
            str(item.get(k) or "") for k in ("title", "source", "displayed_link")
        )
        h = handle_from_text(blob)
        if h:
            return h
    return None


def _shortcode(url: str) -> str:
    m = SHORTCODE.search(url or "")
    return m.group(1) if m else ""


def parse_linkedin_results(body: dict) -> list[Candidate]:
    """Keep /in/ profile hits; drop jobs, companies, posts, and directory pages."""
    out: list[Candidate] = []
    seen: set[str] = set()
    for item in body.get("organic_results") or []:
        if not isinstance(item, dict):
            continue
        page = item.get("link") or ""
        if not _is_profile(page):
            continue
        key = page.split("?")[0].rstrip("/").lower()
        if key in seen:
            continue
        seen.add(key)
        image = item.get("thumbnail") or ""
        out.append(
            Candidate(
                page_url=page,
                image_url=image if str(image).startswith("https://") else "",
                thumbnail_url=item.get("thumbnail") or "",
                title=(item.get("title") or "")[:500],
                source="linkedin-search",
            )
        )
    return out


def _is_profile(url: str) -> bool:
    host = registrable_host(url)
    if host != "linkedin.com" and not host.endswith(".linkedin.com"):
        return False
    try:
        path = urlsplit(url).path or ""
    except ValueError:
        return False
    return bool(IN_PATH.match(path))
