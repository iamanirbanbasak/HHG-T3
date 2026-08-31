"""Domain exception hierarchy.

Frozen contract from `agent-prompts/02-architecture-execution.md` section 4. Every failure in the
system surfaces as one of these seven types; nothing outside this module inherits from `Exception`
directly.

Two behavioural rules matter more than the classes themselves:

- `SearchProviderError` is never converted into an empty result. A broken API key and a genuine
  "no matches" are different outcomes (FR-052, HC-17).
- `EvidenceIntegrityError` is the *success* condition of ``verify --tamper`` and the *failure*
  condition of plain ``verify``. The CLI maps them to different exit codes.
"""

from __future__ import annotations

from typing import Any


class FaceChainError(Exception):
    """Base for every domain error raised by this project."""

    def __init__(self, message: str, context: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.context = context or {}

    def __str__(self) -> str:
        if not self.context:
            return self.message
        detail = ", ".join(f"{k}={v!r}" for k, v in sorted(self.context.items()))
        return f"{self.message} ({detail})"


class NoFaceDetectedError(FaceChainError):
    """Step 1: the probe image has no detectable face.

    Never worked around by fabricating a detection or a synthetic embedding.
    """


class SearchProviderError(FaceChainError):
    """Step 3: SerpAPI or imgbb returned an error.

    Distinct from an empty result set. Never collapsed into ``[]`` (FR-052).
    """


class CandidateFetchError(FaceChainError):
    """Step 4: a candidate image could not be retrieved.

    Scoped to a single candidate. Logged and skipped; the run continues (FR-053).
    """


class NoVerifiedMatchError(FaceChainError):
    """Step 4: zero candidates cleared the similarity threshold.

    A legitimate, expected outcome. The pipeline never lowers the threshold or falls back to a
    best-available candidate to avoid raising this.
    """


class ChainError(FaceChainError):
    """Steps 6-7: RPC failure, transaction revert, or receipt failure."""


class EvidenceIntegrityError(FaceChainError):
    """Step 7: the recomputed evidence hash does not match the on-chain record."""
