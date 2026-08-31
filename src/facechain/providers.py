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


class LensSearch(Protocol):
    def __call__(self, image_url: str, cfg: Config) -> list[Candidate]: ...


class ImageUpload(Protocol):
    def __call__(self, path: Path, cfg: Config) -> str: ...


@dataclass(frozen=True)
class Providers:
    """Real implementations by default."""

    lens_search: LensSearch
    image_upload: ImageUpload
    fetch_image: Callable[..., Path]


def default_providers() -> Providers:
    from .search.fetch import fetch_image
    from .search.lens import search
    from .search.uploader import upload

    return Providers(lens_search=search, image_upload=upload, fetch_image=fetch_image)
