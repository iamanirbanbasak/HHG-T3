"""Re-verification against the on-chain record.

The failure mode this module is designed against: a verifier that loads the stored evidence hash
for BOTH sides of the comparison and compares it to itself. That proves nothing and is an easy
accident. Here the on-chain read and the local recompute are separate code paths that meet only
at the final comparison.

Recomputation reads local disk only. No hosted URL is ever re-fetched -- not the imgbb crop
(expired after a day) and not the candidate's platform image (may 403 or be deleted). The only
external call in this module is the eth_call.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

from .chain.registry import Registry
from .config import Config
from .errors import FaceChainError
from .evidence import POST_TEXT, copy_run_dir, evidence_hash, rebuild_from_artifacts


@dataclass(frozen=True)
class VerificationResult:
    onchain_hash: bytes
    recomputed_hash: bytes
    record_id: int
    post_url: str
    similarity_bps: int
    network: str
    tampered: bool

    @property
    def matches(self) -> bool:
        return self.onchain_hash == self.recomputed_hash


def verify_record(
    registry: Registry, record_id: int, run_dir: Path, cfg: Config, tamper: bool = False
) -> VerificationResult:
    """Compare the on-chain hash against one recomputed from local source artifacts."""
    # 1. REAL network read. Removing this makes the whole exercise self-referential.
    record = registry.get(record_id)

    # 2. Independent local recomputation from source files.
    if tamper:
        with tempfile.TemporaryDirectory(prefix="facechain-tamper-") as tmp:
            scratch = copy_run_dir(run_dir, Path(tmp) / "run")
            _mutate_one_byte(scratch / POST_TEXT)
            recomputed = evidence_hash(rebuild_from_artifacts(scratch))
    else:
        recomputed = evidence_hash(rebuild_from_artifacts(run_dir))

    return VerificationResult(
        onchain_hash=record.evidence_hash,
        recomputed_hash=recomputed,
        record_id=record_id,
        post_url=record.post_url,
        similarity_bps=record.similarity_bps,
        network=cfg.network,
        tampered=tamper,
    )


def _mutate_one_byte(path: Path) -> None:
    """Flip a single bit of the SOURCE evidence file.

    Deliberately mutates the source artifact and lets the digest change propagate upward, rather
    than editing `post_text_sha256` inside the bundle. Only source-level mutation demonstrates the
    chain catching a real alteration; editing the digest directly would be a self-referential
    trick that a reviewer reading this code would rightly discount.
    """
    if not path.exists():
        raise FaceChainError("cannot tamper: source artifact missing", {"path": str(path)})
    data = bytearray(path.read_bytes())
    if not data:
        raise FaceChainError("cannot tamper: source artifact is empty", {"path": str(path)})
    data[0] ^= 0x01
    path.write_bytes(bytes(data))
