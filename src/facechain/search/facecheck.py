"""FaceCheck.ID provider -- an actual face search engine.

Why this exists alongside Google Lens: Lens is an *image* matcher. It finds copies of a picture
already in Google's index, and does not recognise a face and go looking for that person. A photo
taken just now has never been indexed, so Lens has nothing to match -- which is precisely what we
observed live (120 candidates, 19 face-verified, best cosine 0.29, all rejected).

FaceCheck.ID runs face recognition over crawled social-media images, so a face that has never
been published as *this exact image* can still be found. That is the capability the "scan a face,
get their accounts" flow actually requires.

Two structural differences from the Lens provider:
  - it accepts a direct multipart upload, so no public image host is needed
  - results carry a base64 thumbnail rather than an image URL, so candidate images need no
    outbound fetch (and cannot 403)

Its own `score` (0-100) is NOT trusted as the match decision. Every candidate is still
independently detected, embedded, and cosine-scored against the probe by our pipeline. The
provider proposes; our embedding disposes.
"""

from __future__ import annotations

import time
from pathlib import Path

import httpx

from ..config import Config
from ..errors import SearchProviderError
from .lens import Candidate

BASE = "https://facecheck.id"
UPLOAD = f"{BASE}/api/upload_pic"
SEARCH = f"{BASE}/api/search"
POLL_INTERVAL_S = 2.0
MAX_POLLS = 60


def _headers(cfg: Config) -> dict[str, str]:
    return {"accept": "application/json", "Authorization": str(cfg.facecheck_key)}


def upload_probe(path: Path, cfg: Config) -> str:
    """Upload the probe image and return the search id."""
    cfg.require("facecheck_key")
    p = Path(path)
    if not p.exists():
        raise SearchProviderError("cannot upload missing file", {"path": str(p)})

    try:
        with p.open("rb") as fh:
            resp = httpx.post(
                UPLOAD,
                headers=_headers(cfg),
                files={"images": (p.name, fh, "application/octet-stream")},
                data={"id_search": ""},
                timeout=cfg.fetch_timeout_s * 6,
            )
    except httpx.TimeoutException as exc:
        raise SearchProviderError("face search upload timed out", {"provider": "facecheck"}) from exc
    except httpx.HTTPError as exc:
        raise SearchProviderError("face search upload failed", {"provider": "facecheck"}) from exc

    if resp.status_code != 200:
        # The status is reported; the API token never is.
        raise SearchProviderError(
            "face search upload returned an error status",
            {"provider": "facecheck", "status": resp.status_code},
        )

    body = _json(resp)
    if body.get("error"):
        raise SearchProviderError(
            "face search upload rejected",
            {"provider": "facecheck", "code": str(body.get("code"))[:40]},
        )

    sid = body.get("id_search")
    if not sid:
        raise SearchProviderError("face search returned no search id", {"provider": "facecheck"})
    return str(sid)


def poll_search(id_search: str, cfg: Config, on_progress=None) -> list[dict]:
    """Poll until the search completes. Returns the raw result items."""
    payload = {
        "id_search": id_search,
        "with_progress": True,
        "status_only": False,
        # demo mode scans a reduced index and consumes no credits
        "demo": bool(cfg.facecheck_demo),
    }

    for _ in range(MAX_POLLS):
        try:
            resp = httpx.post(
                SEARCH, headers=_headers(cfg), json=payload, timeout=cfg.fetch_timeout_s * 6
            )
        except httpx.TimeoutException as exc:
            raise SearchProviderError("face search timed out", {"provider": "facecheck"}) from exc
        except httpx.HTTPError as exc:
            raise SearchProviderError("face search failed", {"provider": "facecheck"}) from exc

        if resp.status_code != 200:
            raise SearchProviderError(
                "face search returned an error status",
                {"provider": "facecheck", "status": resp.status_code},
            )

        body = _json(resp)
        if body.get("error"):
            raise SearchProviderError(
                "face search reported an error",
                {"provider": "facecheck", "detail": str(body["error"])[:160]},
            )

        output = body.get("output")
        if output:
            return list(output.get("items") or [])

        if on_progress:
            on_progress(body.get("progress"), body.get("message"))
        time.sleep(POLL_INTERVAL_S)

    raise SearchProviderError(
        "face search did not complete in time",
        {"provider": "facecheck", "polls": MAX_POLLS},
    )


def search(image: Path, cfg: Config, on_progress=None) -> list[Candidate]:
    """Full provider call: upload the probe, poll, return candidates."""
    items = poll_search(upload_probe(image, cfg), cfg, on_progress=on_progress)
    return parse_items(items)


def parse_items(items: list[dict]) -> list[Candidate]:
    """Map raw result items to Candidates.

    `score` is retained only as provider metadata in `source`. It never decides the match --
    our own embedding does.
    """
    out: list[Candidate] = []
    for it in items or []:
        if not isinstance(it, dict):
            continue
        url = it.get("url") or ""
        if not url:
            continue
        out.append(
            Candidate(
                page_url=url,
                image_url="",  # thumbnails arrive inline, not as URLs
                title=str(it.get("guid") or "")[:200],
                source=f"facecheck score={it.get('score')}",
                image_b64=str(it.get("base64") or "") or None,
            )
        )
    return out


def _json(resp) -> dict:
    try:
        body = resp.json()
    except ValueError as exc:
        raise SearchProviderError(
            "face search returned malformed JSON", {"provider": "facecheck"}
        ) from exc
    return body if isinstance(body, dict) else {}
