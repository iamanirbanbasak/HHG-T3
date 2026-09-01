"""Full pipeline on a local chain with injected fake providers.

Exercises detect -> embed -> search -> candidate verification -> evidence -> anchor -> verify ->
tamper, without touching any external service.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from facechain.chain.compile import compile_registry
from facechain.chain.deploy import deploy, make_web3
from facechain.chain.registry import Registry
from facechain.config import Config
from facechain.errors import NoVerifiedMatchError, SearchProviderError
from facechain.evidence import POST_TEXT, evidence_hash, sha256_file, similarity_bps
from facechain.pipeline import run as run_pipeline
from facechain.providers import Providers
from facechain.verify import verify_record
from tests.fakes import candidate, failing_search, make_fake_providers

FX = Path(__file__).parent / "fixtures"
pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


@pytest.fixture(scope="module")
def chain():
    cfg = Config(network="local")
    w3 = make_web3(cfg)
    addr = deploy(w3, cfg)
    abi, _ = compile_registry()
    return w3, Registry(w3, addr, list(abi))


@pytest.fixture
def providers_returning_the_probe():
    """Candidate images ARE the probe image, so a genuine embedding comparison scores ~1.0.

    Nothing is faked about the face work: real detection and real embedding run on both sides.
    Only the network calls are substituted.
    """
    probe_bytes = (FX / "faces_multi.jpg").read_bytes()
    cands = [candidate("https://www.instagram.com/p/REAL/", "https://cdn.test/a.jpg")]
    return make_fake_providers(cands, image_bytes=probe_bytes)


def test_full_run_then_verify_then_tamper(tmp_path, chain, providers_returning_the_probe):
    _, reg = chain
    provs, calls = providers_returning_the_probe
    cfg = Config(network="local", threshold=0.45, artifacts_dir=str(tmp_path))

    # 1-5: pipeline
    result = run_pipeline(FX / "faces_multi.jpg", cfg, providers=provs)

    # the aligned crop AND the full photo were both searched, crop first
    assert calls["search"] == ["probe_aligned.png", "probe.jpg"]
    # the candidate was genuinely fetched and embedded
    assert len(calls["fetch"]) == 1
    assert result.top.cosine > 0.9

    # every source artifact exists
    for name in ("probe.jpg", "probe_aligned.png", "candidate.jpg", POST_TEXT, "evidence.json"):
        assert (result.run_dir / name).exists(), name

    # 6: anchor
    h = evidence_hash(result.bundle)
    rid, tx = reg.anchor(h, result.top.candidate.page_url, similarity_bps(result.top.cosine))
    assert tx

    # 7: verify against the chain
    res = verify_record(reg, rid, result.run_dir, cfg)
    assert res.matches

    # 7b: tamper -> mismatch, originals intact
    before = {p.name: sha256_file(p) for p in result.run_dir.iterdir() if p.is_file()}
    tampered = verify_record(reg, rid, result.run_dir, cfg, tamper=True)
    after = {p.name: sha256_file(p) for p in result.run_dir.iterdir() if p.is_file()}
    assert tampered.matches is False
    assert before == after


def test_no_verified_match_anchors_nothing(tmp_path):
    """A candidate that is a different face must not clear the threshold."""
    other = (FX / "aligned_112.png").read_bytes()
    provs, _ = make_fake_providers(
        [candidate("https://www.instagram.com/p/OTHER/", "https://cdn.test/b.jpg")],
        image_bytes=other,
    )
    cfg = Config(network="local", threshold=0.45, artifacts_dir=str(tmp_path))
    with pytest.raises(NoVerifiedMatchError) as e:
        run_pipeline(FX / "faces_multi.jpg", cfg, providers=provs)
    assert "threshold" in str(e.value)


def test_provider_failure_propagates_and_is_not_an_empty_result(tmp_path):
    provs, _ = make_fake_providers([])
    provs = Providers(failing_search(500), provs.image_upload, provs.fetch_image)
    cfg = Config(network="local", artifacts_dir=str(tmp_path))
    with pytest.raises(SearchProviderError):
        run_pipeline(FX / "faces_multi.jpg", cfg, providers=provs)


def test_non_social_candidates_are_filtered_out(tmp_path):
    provs, _ = make_fake_providers(
        [candidate("https://www.nytimes.com/story.html", "https://cdn.test/n.jpg")],
        image_bytes=(FX / "faces_multi.jpg").read_bytes(),
    )
    cfg = Config(network="local", artifacts_dir=str(tmp_path))
    with pytest.raises(NoVerifiedMatchError):
        run_pipeline(FX / "faces_multi.jpg", cfg, providers=provs)
