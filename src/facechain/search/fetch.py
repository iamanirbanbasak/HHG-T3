"""Candidate image retrieval.

Candidate URLs come from an external provider, so every byte here is treated as hostile: https
only, no internal addresses, streaming size cap, bounded redirects, explicit timeouts.

A single candidate failing raises CandidateFetchError, which the pipeline logs and skips. One bad
image is not a failed run (FR-053).
"""

from __future__ import annotations

import ipaddress
import socket
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from ..config import Config
from ..errors import CandidateFetchError

BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
IMAGE_MAGIC = (b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n", b"GIF8", b"RIFF", b"BM", b"II*\x00", b"MM\x00*")


def _is_internal(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return True  # unresolvable: treat as unsafe
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            return True
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            return True
    return False


def assert_safe_url(url: str) -> None:
    """Reject non-https schemes and internal addresses (SSRF)."""
    try:
        parts = urlsplit(url)
    except ValueError as exc:
        raise CandidateFetchError("malformed url", {"url": url[:200]}) from exc
    if parts.scheme != "https":
        raise CandidateFetchError("only https is allowed", {"scheme": parts.scheme})
    if not parts.hostname:
        raise CandidateFetchError("url has no host", {"url": url[:200]})
    if _is_internal(parts.hostname):
        raise CandidateFetchError("refusing to fetch an internal address", {"host": parts.hostname})


def looks_like_image(head: bytes) -> bool:
    """Verify against actual bytes, not the declared content-type."""
    return any(head.startswith(m) for m in IMAGE_MAGIC)


def fetch_image(url: str, dest: Path, cfg: Config) -> Path:
    """Download an image with the size cap enforced DURING streaming, not after."""
    assert_safe_url(url)
    headers = {"User-Agent": BROWSER_UA, "Referer": "https://www.google.com/", "Accept": "image/*"}

    try:
        with httpx.stream(
            "GET", url, headers=headers, timeout=cfg.fetch_timeout_s,
            follow_redirects=True, max_redirects=3,
        ) as resp:
            if resp.status_code != 200:
                raise CandidateFetchError(
                    "candidate image request failed",
                    {"status": resp.status_code, "url": url[:200]},
                )
            total = 0
            chunks: list[bytes] = []
            for chunk in resp.iter_bytes(65536):
                total += len(chunk)
                if total > cfg.max_image_bytes:
                    raise CandidateFetchError(
                        "candidate image exceeds size cap",
                        {"cap": cfg.max_image_bytes, "url": url[:200]},
                    )
                chunks.append(chunk)
    except CandidateFetchError:
        raise
    except httpx.TimeoutException as exc:
        raise CandidateFetchError("candidate image timed out", {"url": url[:200]}) from exc
    except httpx.HTTPError as exc:
        raise CandidateFetchError("candidate image fetch failed", {"url": url[:200]}) from exc

    data = b"".join(chunks)
    if not data or not looks_like_image(data[:16]):
        raise CandidateFetchError("response is not a recognisable image", {"url": url[:200]})

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return dest
