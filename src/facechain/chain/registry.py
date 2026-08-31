"""Provider-agnostic wrapper over the deployed FaceMatchRegistry.

The same object works unchanged against eth-tester and Base Sepolia; only the injected Web3
differs. If this file ever needs changing to support a public network, the provider-agnostic
claim was false and the fix belongs in provider construction, not here.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..errors import ChainError


@dataclass(frozen=True)
class Record:
    evidence_hash: bytes
    post_url: str
    similarity_bps: int
    timestamp: int
    submitter: str


class Registry:
    def __init__(self, w3, address: str, abi: list) -> None:
        self._w3 = w3
        self._address = w3.to_checksum_address(address)
        self._c = w3.eth.contract(address=self._address, abi=abi)

    @property
    def address(self) -> str:
        return self._address

    def anchor(self, evidence_hash: bytes, post_url: str, sim_bps: int, account=None) -> tuple[int, str]:
        """Append a record. Returns (record_id, tx_hash)."""
        if len(evidence_hash) != 32:
            raise ChainError("evidence hash must be 32 bytes", {"got": len(evidence_hash)})

        sender = account or self._w3.eth.accounts[0]
        try:
            fn = self._c.functions.anchor(evidence_hash, post_url, sim_bps)
            tx_hash = fn.transact({"from": sender})
            receipt = self._w3.eth.wait_for_transaction_receipt(tx_hash)
        except Exception as exc:  # noqa: BLE001
            raise ChainError("anchor transaction failed", {"error": str(exc)}) from exc

        if receipt["status"] != 1:
            raise ChainError("anchor transaction reverted", {"tx": tx_hash.hex()})

        logs = self._c.events.MatchAnchored().process_receipt(receipt)
        if not logs:
            raise ChainError("anchor emitted no MatchAnchored event", {"tx": tx_hash.hex()})
        return int(logs[0]["args"]["id"]), tx_hash.hex()

    def get(self, record_id: int) -> Record:
        """Read a record from the chain. This is the eth_call that re-verification depends on."""
        try:
            r = self._c.functions.get(record_id).call()
        except Exception as exc:  # noqa: BLE001
            raise ChainError("could not read record", {"id": record_id, "error": str(exc)}) from exc
        return Record(
            evidence_hash=bytes(r[0]),
            post_url=r[1],
            similarity_bps=int(r[2]),
            timestamp=int(r[3]),
            submitter=r[4],
        )

    def count(self) -> int:
        return int(self._c.functions.count().call())

    def verify_onchain(self, record_id: int, candidate: bytes) -> bool:
        return bool(self._c.functions.verify(record_id, candidate).call())
