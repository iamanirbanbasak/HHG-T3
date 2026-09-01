"""Injection point for the two functions that talk to external providers.

Only `lens_search` and `image_upload` reach outside the process. Making them injected callables
means tests substitute fakes from `tests/fakes.py` while production always calls the real
implementations -- so there is never a stub inside `src/` that someone must remember to delete
before submission (HC-04).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

from .config import Config
from .search.lens import Candidate


class FaceSearch(Protocol):
    """Takes a local image PATH, not a URL.

    Each provider owns how it gets the image to the service: the Lens provider uploads to a
    public host first because Lens needs a URL; FaceCheck posts the bytes directly. Hiding that
    inside the provider keeps the imgbb hop out of the pipeline, where it never belonged.
    """

    def __call__(self, image: Path, cfg: Config) -> list[Candidate]: ...


class ImageUpload(Protocol):
    def __call__(self, path: Path, cfg: Config) -> str: ...


@dataclass(frozen=True)
class Providers:
    """Real implementations by default."""

    face_search: FaceSearch
    image_upload: ImageUpload
    fetch_image: Callable[..., Path]


def google_lens_search(image: Path, cfg: Config) -> list[Candidate]:
    """Host the image publicly, then reverse-image-search it."""
    from .search.lens import search
    from .search.uploader import upload

    return search(upload(image, cfg), cfg)


def default_providers(cfg: Config | None = None) -> Providers:
    from .search.fetch import fetch_image
    from .search.uploader import upload

    provider = google_lens_search
    if cfg is not None and cfg.search_provider == "facecheck":
        from .search.facecheck import search as facecheck_search

        provider = facecheck_search
    elif cfg is not None and cfg.search_provider == "yandex":
        from .search.yandex import search as yandex_search

        provider = yandex_search

    return Providers(face_search=provider, image_upload=upload, fetch_image=fetch_image)
