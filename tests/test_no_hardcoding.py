"""HC-04 / FR-055: nothing pre-selected may ship in the production path.

The provider-injection design makes most of this structurally true rather than merely tested:
`src/` contains no fake providers at all, so there is no stub to forget to delete.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src" / "facechain"
PY_FILES = sorted(SRC.rglob("*.py"))
SOCIAL = re.compile(
    r"https?://(www\.)?(instagram|twitter|x|facebook|tiktok|linkedin|threads|reddit|bsky)\.com/\S",
    re.I,
)


def test_no_social_post_url_literal_in_src():
    """A pre-picked result would show up as a concrete post URL in shipped code."""
    hits = [(f.name, m.group(0)) for f in PY_FILES for m in SOCIAL.finditer(f.read_text())]
    assert hits == [], f"hardcoded social URL in production code: {hits}"


def test_no_fake_or_stub_providers_in_src():
    banned = re.compile(r"\b(fake_|stub_|dummy_|mock_|_STUB|FAKE_|DEMO_RESULT|KNOWN_MATCH)\w*")
    hits = [(f.name, m.group(0)) for f in PY_FILES for m in banned.finditer(f.read_text())]
    assert hits == [], f"stub-like identifier in production code: {hits}"


def test_src_never_imports_from_tests():
    for f in PY_FILES:
        tree = ast.parse(f.read_text())
        for node in ast.walk(tree):
            mod = ""
            if isinstance(node, ast.ImportFrom):
                mod = node.module or ""
            elif isinstance(node, ast.Import):
                mod = ",".join(a.name for a in node.names)
            assert "tests" not in mod.split("."), f"{f.name} imports from tests"


def test_no_spike_directory_ships():
    assert not (SRC.parents[1] / "spike").exists(), "throwaway spike/ must be deleted before ship"


def test_default_providers_are_the_real_ones():
    """Production defaults must resolve to the real network-calling implementations."""
    from facechain.config import Config
    from facechain.providers import default_providers, google_lens_search
    from facechain.search.fetch import fetch_image
    from facechain.search.uploader import upload

    p = default_providers(Config())
    assert p.face_search is google_lens_search
    assert p.image_upload is upload
    assert p.fetch_image is fetch_image


def test_facecheck_provider_selected_by_config():
    from facechain.config import Config
    from facechain.providers import default_providers
    from facechain.search.facecheck import search as facecheck_search

    p = default_providers(Config(search_provider="facecheck"))
    assert p.face_search is facecheck_search
