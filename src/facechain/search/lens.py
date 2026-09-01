"""Reverse image search via SerpAPI's Google Lens endpoint.

The single most important behaviour in this module:

    a provider failure raises SearchProviderError -- it NEVER returns []

An empty list means the provider succeeded and reported no matches. Conflating the two would make
a broken API key look like a legitimate negative result, which on a project whose entire claim is
that the search is genuine is the most damaging bug available (FR-052, HC-17).
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from ..config import Config
from ..errors import SearchProviderError

ENDPOINT = "https://serpapi.com/search"


@dataclass(frozen=True)
class Candidate:
    page_url: str
    image_url: str
    title: str
    source: str
    # Some providers return the matched thumbnail inline rather than as a URL. When present it is
    # used directly, which avoids an outbound fetch and the hotlink 403s that plague social CDNs.
    image_b64: str | None = None
    # Lower-resolution fallback, used when the full-size original cannot be fetched.
    thumbnail_url: str = ""


def search(image_url: str, cfg: Config) -> list[Candidate]:
    """Run one Google Lens query against a publicly reachable image URL."""
    cfg.require("serpapi_key")
    params = {
        "engine": "google_lens",
        "url": image_url,
        "api_key": str(cfg.serpapi_key),
        "hl": "en",
    }

    try:
        resp = httpx.get(ENDPOINT, params=params, timeout=cfg.fetch_timeout_s * 3)
    except httpx.TimeoutException as exc:
        raise SearchProviderError("lens request timed out", {"provider": "serpapi"}) from exc
    except httpx.HTTPError as exc:
        raise SearchProviderError("lens request failed", {"provider": "serpapi"}) from exc

    # Note: the status is reported, never the API key.
    if resp.status_code != 200:
        raise SearchProviderError(
            "lens returned an error status",
            {"provider": "serpapi", "status": resp.status_code},
        )

    try:
        body = resp.json()
    except ValueError as exc:
        raise SearchProviderError("lens returned malformed JSON", {"provider": "serpapi"}) from exc

    if "error" in body:
        raise SearchProviderError(
            "lens reported an error", {"provider": "serpapi", "detail": str(body["error"])[:200]}
        )

    return parse_candidates(body)


def parse_candidates(body: dict) -> list[Candidate]:
    """Extract candidates from a Lens response.

    Parses defensively: the observed response shape is one sample, not a contract. A successful
    response with no matches legitimately yields [].
    """
    out: list[Candidate] = []
    for key in ("visual_matches", "image_results", "inline_images"):
        for item in body.get(key) or []:
            if not isinstance(item, dict):
                continue
            page = item.get("link") or item.get("source_url") or ""
            if not page:
                continue
            out.append(
                Candidate(
                    page_url=page,
                    # Prefer the full-resolution source over the thumbnail. Lens thumbnails are
                    # ~200px, and after face-cropping and upscaling to 112x112 that discards
                    # detail the embedding depends on. The thumbnail is a fallback, not a choice.
                    image_url=item.get("original") or item.get("thumbnail") or "",
                    thumbnail_url=item.get("thumbnail") or "",
                    title=(item.get("title") or "")[:500],
                    source=(item.get("source") or "")[:200],
                )
            )
    return out
