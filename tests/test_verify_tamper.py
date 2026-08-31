"""Re-verification and tamper tests.

With test_evidence.py, these protect the actual claim made to judges.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from facechain.chain.compile import compile_registry
from facechain.chain.deploy import deploy, make_web3
from facechain.chain.registry import Registry
from facechain.config import Config
from facechain.evidence import POST_TEXT, evidence_hash, rebuild_from_artifacts, sha256_file
from facechain.verify import verify_record


@pytest.fixture(scope="module")
def chain():
    cfg = Config(network="local")
    w3 = make_web3(cfg)
    addr = deploy(w3, cfg)
    abi, _ = compile_registry()
    return w3, Registry(w3, addr, list(abi)), cfg


@pytest.fixture
def anchored(chain, written_run):
    _, reg, cfg = chain
    h = evidence_hash(rebuild_from_artifacts(written_run))
    rid, _ = reg.anchor(h, "https://www.instagram.com/p/EXAMPLE/", 7123)
    return reg, rid, written_run, cfg


class TestVerify:
    def test_round_trip_matches(self, anchored):
        reg, rid, run_dir, cfg = anchored
        res = verify_record(reg, rid, run_dir, cfg)
        assert res.matches
        assert res.onchain_hash == res.recomputed_hash

    def test_reads_from_chain(self, anchored, monkeypatch):
        """ANTI-CHEAT: verification must fail if the on-chain read is neutralised.

        If this passes with a stubbed eth_call, verification is self-comparison and HC-13 is
        hollow.
        """
        reg, rid, run_dir, cfg = anchored
        from facechain.chain.registry import Record

        monkeypatch.setattr(
            reg, "get",
            lambda _id: Record(b"\x00" * 32, "https://x/", 0, 1, "0x" + "0" * 40),
        )
        assert verify_record(reg, rid, run_dir, cfg).matches is False

    def test_corrupted_artifact_causes_mismatch(self, anchored):
        reg, rid, run_dir, cfg = anchored
        (run_dir / POST_TEXT).write_text("this is not the original evidence")
        assert verify_record(reg, rid, run_dir, cfg).matches is False

    def test_offline_verify_makes_no_http_calls(self, anchored, monkeypatch):
        """ANTI-CHEAT: the only external call permitted is the eth_call."""
        import httpx

        def boom(*a, **k):
            raise AssertionError("verification must not make HTTP requests")

        monkeypatch.setattr(httpx, "get", boom)
        monkeypatch.setattr(httpx, "post", boom)
        monkeypatch.setattr(httpx, "stream", boom)
        reg, rid, run_dir, cfg = anchored
        assert verify_record(reg, rid, run_dir, cfg).matches


class TestTamper:
    def test_tamper_produces_mismatch(self, anchored):
        reg, rid, run_dir, cfg = anchored
        res = verify_record(reg, rid, run_dir, cfg, tamper=True)
        assert res.matches is False
        assert res.tampered is True

    def test_originals_are_byte_identical_afterwards(self, anchored):
        """The tamper demo must never corrupt real evidence."""
        reg, rid, run_dir, cfg = anchored
        before = {p.name: sha256_file(p) for p in sorted(run_dir.iterdir()) if p.is_file()}
        verify_record(reg, rid, run_dir, cfg, tamper=True)
        after = {p.name: sha256_file(p) for p in sorted(run_dir.iterdir()) if p.is_file()}
        assert before == after

    def test_mutates_source_not_the_stored_digest(self, anchored):
        """ANTI-CHEAT: the mutation happens at source-evidence level.

        After a tamper run the stored bundle's digest field is unchanged on disk -- proving the
        mismatch came from re-hashing altered source bytes, not from editing a digest.
        """
        reg, rid, run_dir, cfg = anchored
        digest_before = json.loads((run_dir / "evidence.json").read_text())["match"]["post_text_sha256"]
        verify_record(reg, rid, run_dir, cfg, tamper=True)
        digest_after = json.loads((run_dir / "evidence.json").read_text())["match"]["post_text_sha256"]
        assert digest_before == digest_after == sha256_file(run_dir / POST_TEXT)

    def test_plain_verify_still_matches_after_tamper_demo(self, anchored):
        reg, rid, run_dir, cfg = anchored
        verify_record(reg, rid, run_dir, cfg, tamper=True)
        assert verify_record(reg, rid, run_dir, cfg).matches
