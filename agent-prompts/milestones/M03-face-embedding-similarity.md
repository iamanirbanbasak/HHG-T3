# Milestone M03 — Face Embedding & Similarity

## Objective

Implement `face.embed` (512-d L2-normalised ArcFace embedding) and `face.similarity` (cosine).

## Why This Milestone Exists

HC-02 requires a real embedding. HC-07 requires numeric similarity. These two functions are what
later make the embedding load-bearing rather than decorative — without them M09 cannot exist.

## Requirements Covered

Owns: FR-007, FR-008, FR-009.

## Preconditions

M02 `PASS`.

## Inputs

`02` §3.2, §3.3. Aligned crops from M02.

## Expected Repository State Before Starting

`face/detect.py` and `face/models.py` exist; suite green.

## Files To Create

```text
src/facechain/face/embed.py
src/facechain/face/similarity.py
tests/test_embed.py
tests/test_similarity.py
```

## Files To Modify

`src/facechain/face/__init__.py`.

## Files That Must Not Be Modified

`face/detect.py` (stable contract), `config.py`, `errors.py`.

## Implementation Tasks

### Task 1 — `embed`

Reuse the cached `buffalo_l` recognition model from `models.py`. Input is a 112x112 aligned crop;
output is `(512,)` float32.

### Task 2 — L2 normalisation

Normalise before returning. `abs(norm(v) - 1.0) < 1e-5`. Cosine similarity on unnormalised
vectors is a silent correctness bug that would distort every threshold decision downstream.

### Task 3 — `cosine`

Pure function. numpy only. No I/O, no config, no model. Symmetric, bounded `[-1, 1]`, returns
1.0 for identical vectors and ~0.0 for orthogonal ones.

## Technical Constraints

`similarity.py` imports **only** numpy. It is the most-tested and least-coupled module in the
project; keep it that way.

## Interfaces / Contracts

`02` §3.2, §3.3, exactly.

## Error Handling

Wrong-shaped input raises `FaceChainError` naming the expected shape. Never silently reshape or
pad — that would mask a real upstream bug.

## Performance Requirements

Embedding under ~80ms per face after warm-up. Recognition model loads once (NFR-002).

## Accuracy Requirements

Two different aligned crops of the **same** person score meaningfully higher than crops of two
different people. Record both numbers in the agent report. This is a smoke check, not the M12
calibration.

## Security Requirements

Embeddings are biometric data. Do not persist raw embeddings anywhere in this milestone — the
bundle stores only a digest (see `09` §Privacy).

## Tests To Add

### Unit Tests
Shape `(512,)` and dtype float32; L2 norm within tolerance; cosine identical → 1.0; orthogonal →
0.0; symmetry `cosine(a,b) == cosine(b,a)`; bounded output on random vectors.

### Integration Tests
Detect → align → embed on a real fixture produces a valid normalised vector.

### End-to-End Tests
None.

### Regression Tests
Full suite.

### Failure Tests
Wrong shape raises; empty array raises.

### Performance Tests
Warm embedding latency recorded.

### Accuracy Tests
Same-person pair scores above a different-person pair. Numbers recorded, not asserted as a
threshold.

## Commands To Run

```bash
uv run pytest tests/test_embed.py tests/test_similarity.py -v
uv run pytest -q
```

## Acceptance Criteria

| # | Criterion | Evidence |
|---|---|---|
| 1 | 512-d float32 output | pytest |
| 2 | L2-normalised | pytest |
| 3 | Cosine correct, symmetric, bounded | pytest |
| 4 | Same-person > different-person | agent report numbers |
| 5 | Model loads once | pytest |

## Exit Gate

```text
MILESTONE STATUS: PASS | BLOCKED | FAILED
```

## Failure Conditions

Unnormalised vectors; cosine outside `[-1, 1]`; same-person scoring below different-person, which
would indicate a broken alignment or the wrong model head.

## Rollback Strategy

Revert `embed.py` and `similarity.py`. M02 unaffected.

## Documentation Updates

`.agent-state`. Note observed same/different scores — M12 starts from them.

## Required Agent Report

Standard, plus the two similarity numbers from the accuracy check.

## Questions That Require User Input

None expected.

## Definition of Done

Five criteria met; observed similarity separation recorded for M12.
