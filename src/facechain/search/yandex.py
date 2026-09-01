"""Yandex reverse image search, scraped with Scrapling.

Why this provider exists: Google Lens optimises for products and scenes. Given a photo of a
person in distinctive clothing it returns shopping results -- a real run produced 60 garment
listings and never attempted the face. Yandex's image search indexes people-pages far more
readily; the same probe returned YouTube channels, Behance and ResearchGate profiles, and Xing
pages.

It is a different index with different coverage, which is the point. Better coverage of ordinary
people comes from searching somewhere else, not from a better model over the same index.

Trade-offs, stated plainly because they are real:

  - Yandex has no public API, so this scrapes rendered HTML. It is best-effort and WILL break
    when Yandex changes its markup. It is an additional provider, never a replacement for the
    API-backed one.
  - Browser automation costs 10-20s per query versus ~3s for an API.
  - Automated access is contrary to Yandex's terms. The task explicitly permits "a scripted
    search approach"; the README says this provider scrapes.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qsl, quote_plus, urlencode, urlsplit, urlunsplit

from ..config import Config
from ..errors import SearchProviderError
from .lens import Candidate

SEARCH_URL = "https://yandex.com/images/search"
# "sites" lists pages CONTAINING the image. "similar" returns look-alike images with no page
# links, which is useless here.
CBIR_PAGE = "sites"
FETCH_TIMEOUT_MS = 60_000

# Tracking parameters Yandex appends to every outbound link.
JUNK_PARAMS = {"utm_medium", "utm_source", "utm_campaign", "_escaped_fragment_"}


def clean_url(url: str) -> str:
    """Strip Yandex's tracking parameters, keeping the rest of the query intact."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return url
    kept = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
            if k not in JUNK_PARAMS]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(kept), ""))


def build_query_url(image_url: str) -> str:
    return f"{SEARCH_URL}?rpt=imageview&url={quote_plus(image_url)}&cbir_page={CBIR_PAGE}"


def parse_results(html: str) -> list[Candidate]:
    """Extract candidates from a rendered Yandex results page."""
    from scrapling.parser import Selector

    out: list[Candidate] = []
    for item in Selector(html).css(".CbirSites-Item"):
        title_a = item.css(".CbirSites-ItemTitle a")
        if not title_a:
            continue
        href = title_a[0].attrib.get("href") or ""
        if not href.startswith("http"):
            continue

        domain_a = item.css("a.CbirSites-ItemDomain")
        thumb = item.css(".CbirSites-ItemThumb img")

        out.append(
            Candidate(
                page_url=clean_url(href),
                # Yandex serves its own thumbnails, so these do not 403 the way social CDNs do.
                image_url=_abs(thumb[0].attrib.get("src") or "") if thumb else "",
                title=str(title_a[0].text or "").strip()[:500],
                source=f"yandex {str(domain_a[0].text).strip()[:60]}" if domain_a else "yandex",
            )
        )
    return out


def _abs(src: str) -> str:
    if src.startswith("//"):
        return "https:" + src
    return src


def is_bot_challenged(html: str) -> bool:
    low = html.lower()
    return any(s in low for s in ("showcaptcha", "are you a robot", "confirm you are not a robot"))


def search(image: Path, cfg: Config, hosted_url: str | None = None) -> list[Candidate]:
    """Reverse-image-search a local file via Yandex.

    Yandex needs a publicly reachable URL, so the image is hosted first -- the same hop the Lens
    provider uses.
    """
    from .uploader import upload

    url = hosted_url or upload(Path(image), cfg)

    try:
        from scrapling.fetchers import StealthyFetcher
    except ImportError as exc:  # pragma: no cover
        raise SearchProviderError(
            "scrapling is not installed", {"hint": "uv pip install 'scrapling[fetchers]'"}
        ) from exc

    try:
        page = StealthyFetcher.fetch(
            build_query_url(url), headless=True, network_idle=True, timeout=FETCH_TIMEOUT_MS
        )
    except Exception as exc:  # noqa: BLE001
        raise SearchProviderError(
            "yandex fetch failed", {"provider": "yandex", "error": str(exc)[:160]}
        ) from exc

    status = getattr(page, "status", 0)
    if status != 200:
        raise SearchProviderError(
            "yandex returned an error status", {"provider": "yandex", "status": status}
        )

    html = page.html_content or ""
    if is_bot_challenged(html):
        # A bot challenge is a PROVIDER FAILURE, never an empty result set. Reporting it as
        # "found nothing" would make a blocked scrape look like a genuine negative.
        raise SearchProviderError(
            "yandex served a bot challenge", {"provider": "yandex", "hint": "retry later"}
        )

    return parse_results(html)
