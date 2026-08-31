from __future__ import annotations

import json
from pathlib import Path

import pytest

from facechain.config import Config
from facechain.evidence import (
    CANDIDATE_IMAGE,
    POST_TEXT,
    PROBE_ALIGNED,
    PROBE_IMAGE,
    canonicalise,
)


@pytest.fixture
def cfg() -> Config:
    """A Config built directly, never from the environment."""
    return Config(network="local", threshold=0.45)


@pytest.fixture
def run_dir(tmp_path: Path) -> Path:
    """A synthetic run directory with all four source artifacts present."""
    d = tmp_path / "run-test"
    d.mkdir()
    (d / PROBE_IMAGE).write_bytes(b"fake-probe-image-bytes")
    (d / PROBE_ALIGNED).write_bytes(b"fake-aligned-crop-bytes")
    (d / CANDIDATE_IMAGE).write_bytes(b"fake-candidate-image-bytes")
    (d / POST_TEXT).write_text("a real post caption that the tamper demo will mutate\n")
    return d


@pytest.fixture
def bundle(run_dir: Path) -> dict:
    from facechain.evidence import build_bundle

    return build_bundle(
        run_dir=run_dir,
        bbox=(10, 20, 100, 120),
        det_score=0.94,
        faces_detected=1,
        embedding_sha256="a" * 64,
        query_image_sha256="b" * 64,
        n_candidates=27,
        n_social=9,
        n_face_verified=3,
        post_url="https://www.instagram.com/p/EXAMPLE/",
        platform="instagram",
        author_handle="example",
        image_url="https://cdn.example.com/i.jpg",
        cosine=0.7123,
        threshold=0.45,
        queried_at="2026-09-01T12:00:00Z",
        captured_at="2026-09-01T12:00:04Z",
    )


@pytest.fixture
def written_run(run_dir: Path, bundle: dict) -> Path:
    (run_dir / "evidence.json").write_bytes(canonicalise(bundle))
    return run_dir
