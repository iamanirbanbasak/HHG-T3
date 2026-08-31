"""Contract integration tests. eth-tester in-process: no RPC, no binary, no network."""

from __future__ import annotations

import pytest

from facechain.chain.compile import compile_registry
from facechain.chain.deploy import connect, deploy, make_web3
from facechain.chain.registry import Registry
from facechain.config import Config
from facechain.errors import ChainError

HASH_A = bytes.fromhex("11" * 32)
HASH_B = bytes.fromhex("22" * 32)
URL = "https://www.instagram.com/p/EXAMPLE/"


@pytest.fixture(scope="module")
def chain():
    cfg = Config(network="local")
    w3 = make_web3(cfg)
    address = deploy(w3, cfg)
    abi, _ = compile_registry()
    return w3, Registry(w3, address, list(abi)), cfg


def test_compiles_with_pinned_solc():
    abi, bytecode = compile_registry()
    assert len(abi) > 0 and bytecode.startswith("6080") or len(bytecode) > 100
    names = {e.get("name") for e in abi}
    assert {"anchor", "get", "count", "verify"} <= names


def test_deploys_local(chain):
    _, reg, _ = chain
    assert reg.address.startswith("0x") and len(reg.address) == 42


def test_anchor_emits_event_and_returns_id(chain):
    _, reg, _ = chain
    rid, tx = reg.anchor(HASH_A, URL, 7123)
    assert isinstance(rid, int) and rid >= 0
    assert tx


def test_readback_round_trips_every_field(chain):
    _, reg, _ = chain
    rid, _ = reg.anchor(HASH_B, URL, 4500)
    rec = reg.get(rid)
    assert rec.evidence_hash == HASH_B
    assert rec.post_url == URL
    assert rec.similarity_bps == 4500
    assert rec.timestamp > 0
    assert rec.submitter.startswith("0x")


def test_count_increments(chain):
    _, reg, _ = chain
    before = reg.count()
    reg.anchor(HASH_A, URL, 5000)
    assert reg.count() == before + 1


def test_onchain_verify(chain):
    _, reg, _ = chain
    rid, _ = reg.anchor(HASH_A, URL, 6000)
    assert reg.verify_onchain(rid, HASH_A) is True
    assert reg.verify_onchain(rid, HASH_B) is False


def test_rejects_empty_hash(chain):
    _, reg, _ = chain
    with pytest.raises(ChainError):
        reg.anchor(b"\x00" * 32, URL, 5000)


def test_rejects_empty_url(chain):
    _, reg, _ = chain
    with pytest.raises(ChainError):
        reg.anchor(HASH_A, "", 5000)


def test_rejects_wrong_hash_length(chain):
    _, reg, _ = chain
    with pytest.raises(ChainError):
        reg.anchor(b"\x11" * 16, URL, 5000)


def test_no_mutation_path_in_abi():
    """Append-only. A setter or delete would defeat the entire point of the record."""
    abi, _ = compile_registry()
    fns = {e.get("name") for e in abi if e.get("type") == "function"}
    forbidden = {"set", "update", "delete", "remove", "edit", "setRecord", "transferOwnership"}
    assert not (fns & forbidden)
    mutating = {
        e.get("name") for e in abi
        if e.get("type") == "function" and e.get("stateMutability") in ("nonpayable", "payable")
    }
    assert mutating == {"anchor"}


def test_unknown_record_raises(chain):
    _, reg, _ = chain
    with pytest.raises(ChainError):
        reg.get(9999)


def test_similarity_bps_boundaries_fit_uint16(chain):
    _, reg, _ = chain
    for bps in (0, 1, 4500, 10000):
        rid, _ = reg.anchor(HASH_A, URL, bps)
        assert reg.get(rid).similarity_bps == bps
