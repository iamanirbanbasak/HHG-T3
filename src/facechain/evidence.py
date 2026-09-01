"""Evidence bundle assembly, canonical serialisation, and hashing.

Two hash algorithms are used, deliberately kept separate (spec section 5.2):

- SHA-256 for individual artifact digests. The natural choice for file digests.
- keccak256 for the on-chain bundle hash. The EVM-native word.

Each is used in exactly one place. Do not merge them.

The canonical form is not optional. Without stable key ordering and tight separators,
re-verification fails on serialisation noise rather than on tampering -- and that failure looks
exactly like a real tamper detection, which is worse than having no check at all.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from eth_utils import keccak

from .errors import FaceChainError

SCHEMA = "hhg-t3/evidence/v1"

# The models actually shipped in the buffalo_l pack, verified at runtime.
#
# DEVIATION from spec section 5.1, recorded deliberately: the spec names
# "arcface_r100_glint360k" as the embedder, but buffalo_l ships w600k_r50. The evidence bundle
# attests to which models produced the embedding, so it must name the model that actually ran.
# Claiming r100 while running r50 would make the bundle inaccurate about its own provenance.
MODELS = {
    "detector": "scrfd_10g_bnkps",
    "embedder": "w600k_r50",
    "pack": "buffalo_l",
}

# Artifact filenames, frozen by 02-architecture-execution.md section 9.
PROBE_IMAGE = "probe.jpg"
PROBE_ALIGNED = "probe_aligned.png"
PROBE_HEAD = "probe_head.png"
CANDIDATE_IMAGE = "candidate.jpg"
POST_TEXT = "post_text.txt"
EVIDENCE_JSON = "evidence.json"
RECEIPT_JSON = "receipt.json"


def canonicalise(bundle: dict[str, Any]) -> bytes:
    """Serialise deterministically.

    Exactly this form, everywhere. Byte-stable across key orderings and across processes.
    """
    return json.dumps(
        bundle, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")


def evidence_hash(bundle: dict[str, Any]) -> bytes:
    """keccak256 of the canonical bundle bytes. 32 bytes, Solidity-native."""
    return keccak(canonicalise(bundle))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    """SHA-256 of a file's contents, lowercase hex, no prefix."""
    if not path.exists():
        raise FaceChainError("artifact missing", {"path": str(path)})
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def similarity_bps(cosine: float) -> int:
    """Encode a cosine similarity as basis points for on-chain storage.

    This is a RAW COSINE ENCODING, not a probability and not a confidence percentage. A value of
    10000 means cosine 1.0 -- it does not mean "100% certain". This matters because the on-chain
    value is the one artifact a reviewer sees without the README beside it.

    Cosine can be negative for non-matching faces; clamping at zero keeps the on-chain type
    unsigned and loses no information, since anything anchored already cleared a positive
    threshold.
    """
    return max(0, min(10000, round(cosine * 10000)))


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_bundle(
    *,
    run_dir: Path,
    bbox: tuple[int, int, int, int],
    det_score: float,
    faces_detected: int,
    embedding_sha256: str,
    query_image_sha256: str,
    n_candidates: int,
    n_social: int,
    n_face_verified: int,
    post_url: str,
    platform: str,
    author_handle: str,
    image_url: str,
    cosine: float,
    threshold: float,
    queried_at: str,
    captured_at: str,
    provider: str = "serpapi/google_lens",
) -> dict[str, Any]:
    """Assemble the hhg-t3/evidence/v1 bundle.

    Every digest is computed from the stored source files in ``run_dir``, never passed in.
    """
    return {
        "schema": SCHEMA,
        "probe": {
            "image_sha256": sha256_file(run_dir / PROBE_IMAGE),
            "bbox": list(bbox),
            "det_score": round(float(det_score), 6),
            "embedding_sha256": embedding_sha256,
            "faces_detected": faces_detected,
            "models": MODELS,
        },
        "search": {
            "provider": provider,
            "queried_at": queried_at,
            "query_image_sha256": query_image_sha256,
            "queries": ["face_crop", "full_photo"],
            "n_candidates": n_candidates,
            "n_social": n_social,
            "n_face_verified": n_face_verified,
        },
        "match": {
            "post_url": post_url,
            "platform": platform,
            "author_handle": author_handle,
            "image_url": image_url,
            "image_sha256": sha256_file(run_dir / CANDIDATE_IMAGE),
            "post_text_sha256": sha256_file(run_dir / POST_TEXT),
            "captured_at": captured_at,
        },
        "verification": {
            "cosine_similarity": round(float(cosine), 6),
            "threshold": float(threshold),
            "passed": bool(cosine >= threshold),
        },
    }


def rebuild_from_artifacts(run_dir: Path) -> dict[str, Any]:
    """Reconstruct the bundle by recomputing every digest from the stored SOURCE FILES.

    This is the function the whole re-verification claim rests on, and the one an adversarial
    reviewer reads first.

    It reads the non-digest metadata from the stored bundle (URLs, timestamps, scores -- values
    that have no independent source on disk), but it NEVER reuses a stored digest. All three
    digests are recomputed from probe.jpg, candidate.jpg, and post_text.txt. That is what makes a
    mutation of any source artifact produce a different bundle hash.

    Reads local disk only. No hosted URL is ever re-fetched: not the imgbb query crop (expired
    after a day) and not the candidate's platform image (may 403 or be deleted). Verification must
    keep working indefinitely, offline, with only the RPC endpoint reachable.
    """
    stored_path = run_dir / EVIDENCE_JSON
    if not stored_path.exists():
        raise FaceChainError("evidence bundle missing", {"path": str(stored_path)})

    try:
        stored = json.loads(stored_path.read_text())
    except json.JSONDecodeError as exc:
        raise FaceChainError("evidence bundle is not valid JSON", {"path": str(stored_path)}) from exc

    for section in ("schema", "probe", "search", "match", "verification"):
        if section not in stored:
            raise FaceChainError("evidence bundle malformed", {"missing_key": section})

    rebuilt = json.loads(json.dumps(stored))  # deep copy

    # The three digests are RECOMPUTED, never carried over.
    rebuilt["probe"]["image_sha256"] = sha256_file(run_dir / PROBE_IMAGE)
    rebuilt["match"]["image_sha256"] = sha256_file(run_dir / CANDIDATE_IMAGE)
    rebuilt["match"]["post_text_sha256"] = sha256_file(run_dir / POST_TEXT)
    return rebuilt


def write_bundle(run_dir: Path, bundle: dict[str, Any]) -> Path:
    path = run_dir / EVIDENCE_JSON
    path.write_bytes(canonicalise(bundle))
    return path


def copy_run_dir(run_dir: Path, dest: Path) -> Path:
    """Copy a run directory so a tamper demonstration never touches real evidence."""
    shutil.copytree(run_dir, dest, dirs_exist_ok=True)
    return dest
