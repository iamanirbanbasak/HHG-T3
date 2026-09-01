"""Local-signing path for public networks.

This exists because the public-network path was broken and no test covered it: `anchor` used
`w3.eth.accounts[0]` and `transact()`, but a public RPC holds no keys -- `eth.accounts` is empty
and `eth_sendTransaction` is refused. Every testnet anchor would have failed.

These tests drive the same build/sign/send-raw code the testnet uses, against eth-tester.
"""

from __future__ import annotations

import pytest
from eth_account import Account

from facechain.chain.compile import compile_registry
from facechain.chain.deploy import deploy, make_web3, signing_account
from facechain.chain.registry import Registry
from facechain.config import Config
from facechain.errors import ChainError

HASH = bytes.fromhex("ab" * 32)
URL = "https://example.com/p/1"


@pytest.fixture(scope="module")
def chain():
    cfg = Config(network="local")
    w3 = make_web3(cfg)
    addr = deploy(w3, cfg)
    abi, _ = compile_registry()
    return w3, addr, list(abi)


@pytest.fixture
def funded_account(chain):
    """A local key with a balance, mirroring a funded testnet wallet."""
    w3, _, _ = chain
    acct = Account.create()
    w3.eth.send_transaction({
        "from": w3.eth.accounts[0], "to": acct.address, "value": w3.to_wei(1, "ether"),
    })
    return acct


class TestLocalSigning:
    def test_anchor_with_a_locally_signed_transaction(self, chain, funded_account):
        w3, addr, abi = chain
        reg = Registry(w3, addr, abi, account=funded_account)
        rid, tx = reg.anchor(HASH, URL, 7000)
        assert isinstance(rid, int) and tx

    def test_signed_record_reads_back_with_the_signer_as_submitter(self, chain, funded_account):
        w3, addr, abi = chain
        reg = Registry(w3, addr, abi, account=funded_account)
        rid, _ = reg.anchor(HASH, URL, 8100)
        rec = reg.get(rid)
        assert rec.evidence_hash == HASH
        assert rec.similarity_bps == 8100
        assert rec.submitter.lower() == funded_account.address.lower()

    def test_nonce_advances_across_two_signed_anchors(self, chain, funded_account):
        w3, addr, abi = chain
        reg = Registry(w3, addr, abi, account=funded_account)
        before = w3.eth.get_transaction_count(funded_account.address)
        reg.anchor(HASH, URL, 100)
        reg.anchor(HASH, URL, 200)
        assert w3.eth.get_transaction_count(funded_account.address) == before + 2


class TestPublicNetworkGuards:
    def test_no_signer_and_no_node_accounts_gives_an_actionable_error(self, chain, monkeypatch):
        """The exact failure a public RPC produces, surfaced as guidance not an IndexError."""
        w3, addr, abi = chain
        reg = Registry(w3, addr, abi)  # no account
        monkeypatch.setattr(type(w3.eth), "accounts", property(lambda self: []))
        with pytest.raises(ChainError) as e:
            reg.anchor(HASH, URL, 5000)
        assert "private key" in str(e.value).lower()

    def test_signing_account_is_none_for_local(self, chain):
        w3, _, _ = chain
        assert signing_account(w3, Config(network="local")) is None

    def test_signing_account_required_for_public_network(self, chain):
        w3, _, _ = chain
        from facechain.errors import FaceChainError

        with pytest.raises(FaceChainError):
            signing_account(w3, Config(network="base-sepolia"))

    def test_signing_account_derived_from_private_key(self, chain):
        w3, _, _ = chain
        key = "0x" + "11" * 32
        acct = signing_account(w3, Config(network="base-sepolia", private_key=key))
        assert acct.address == Account.from_key(key).address
