"""Temporary public image hosting (imgbb).

This hop exists for one reason: the Google Lens endpoint accepts an image URL, not raw bytes. It
is the moving part most often underestimated in this pipeline.

Uploads carry a one-day expiry so demo face crops do not persist indefinitely.
"""

from __future__ import annotations

import base64
from pathlib import Path

import httpx

from ..config import Config
from ..errors import SearchProviderError

ENDPOINT = "https://api.imgbb.com/1/upload"
EXPIRY_SECONDS = 86_400


def upload(path: Path, cfg: Config) -> str:
    """Publish an image and return its public HTTPS URL."""
    cfg.require("imgbb_key")
    p = Path(path)
    if not p.exists():
        raise SearchProviderError("cannot upload missing file", {"path": str(p)})

    payload = base64.b64encode(p.read_bytes()).decode("ascii")
    try:
        resp = httpx.post(
            ENDPOINT,
            data={
                "key": str(cfg.imgbb_key),
                "image": payload,
                "expiration": str(EXPIRY_SECONDS),
            },
            timeout=cfg.fetch_timeout_s * 3,
        )
    except httpx.TimeoutException as exc:
        raise SearchProviderError("image upload timed out", {"provider": "imgbb"}) from exc
    except httpx.HTTPError as exc:
        raise SearchProviderError("image upload failed", {"provider": "imgbb"}) from exc

    if resp.status_code != 200:
        raise SearchProviderError(
            "image host returned an error status",
            {"provider": "imgbb", "status": resp.status_code},
        )

    try:
        body = resp.json()
        url = body["data"]["url"]
    except (ValueError, KeyError, TypeError) as exc:
        raise SearchProviderError("image host returned an unexpected body", {"provider": "imgbb"}) from exc

    return str(url)
