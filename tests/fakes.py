"""Fake providers for tests.

These live in tests/, never in src/. Production code always calls the real providers, so there is
no stub inside the shipped package that anyone must remember to delete before submission.
"""

from __future__ import annotations

from pathlib import Path

from facechain.config import Config
from facechain.errors import CandidateFetchError, SearchProviderError
from facechain.providers import Providers
from facechain.search.lens import Candidate


def make_fake_providers(candidates, image_bytes: bytes = b"\xff\xd8\xff\xe0fake-jpeg"):
    calls: dict[str, list] = {"upload": [], "search": [], "fetch": []}

    def upload(path: Path, cfg: Config) -> str:
        calls["upload"].append(Path(path).name)
        return f"https://fake.test/{Path(path).name}"

    def search(image_url: str, cfg: Config):
        calls["search"].append(image_url)
        return list(candidates)

    def fetch(url: str, dest: Path, cfg: Config) -> Path:
        calls["fetch"].append(url)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(image_bytes)
        return dest

    return Providers(lens_search=search, image_upload=upload, fetch_image=fetch), calls


def failing_search(status: int = 500):
    def search(image_url: str, cfg: Config):
        raise SearchProviderError("lens returned an error status", {"status": status})

    return search


def empty_search(image_url: str, cfg: Config):
    """A SUCCESSFUL call that found nothing. Distinct from a provider failure."""
    return []


def failing_fetch(url: str, dest: Path, cfg: Config) -> Path:
    raise CandidateFetchError("candidate image request failed", {"status": 403})


def candidate(page_url: str, image_url: str = "https://cdn.test/i.jpg") -> Candidate:
    return Candidate(page_url=page_url, image_url=image_url, title="t", source="s")
