# Milestone M09 — Candidate Face Verification

## Objective

For every filtered candidate: fetch its image, detect the face, align, embed, score by cosine
against the probe, reject below `tau`, rank, and select the top survivor.

## Why This Milestone Exists

**This is the milestone that makes the face embedding load-bearing.** Without it the project is
an image lookup wearing a face-recognition costume, and HC-03, HC-06, HC-07, HC-08, and HC-09 are
all unsatisfied at once.

The design decision in spec §2 exists precisely for this: the reverse-image query is the face
crop, and every candidate is *independently* re-detected and re-embedded. That second half is
what this milestone builds. A reviewer checking whether the encoding is decorative reads this
code first.

## Requirements Covered

Owns: FR-018, FR-019, FR-020, FR-021, FR-022.

## Preconditions

M03 `PASS` (embedding + cosine), M08 `PASS` (candidates fetched).

## Inputs

Probe embedding from M03. Fetched candidate images from M08. `Config.threshold` (default 0.45).

## Expected Repository State Before Starting

Face pipeline and candidate retrieval both green.

## Files To Create

```text
src/facechain/pipeline.py                 # partial — verification loop only
tests/test_candidate_verification.py
tests/test_pipeline_no_match.py
```

## Files To Modify

None yet — `pipeline.run` is completed at M10.

## Files That Must Not Be Modified

`face/embed.py`, `face/similarity.py` — reuse them exactly. Reimplementing cosine locally is how
the two paths silently diverge.

## Implementation Tasks

### Task 1 — The verification loop

For each candidate, in order:

```text
fetch  →  detect  →  align  →  embed  →  cosine(probe, candidate)  →  threshold
```

Produce a `ScoredCandidate` per `02` §3.7 carrying the candidate, its cosine, and its local image
path.

A candidate whose image contains **no** face is skipped, not scored zero — no face is a different
outcome from a poor match, and scoring it zero would pollute the M12 distributions.

### Task 2 — Threshold and ranking

Reject `cosine < tau` (FR-020). Rank survivors descending. The highest scorer is the match
(FR-021). Exactly one match is anchored per run — anchoring all of them is NG-08.

`tau` comes from `Config.threshold`. **Never hardcode 0.45 in `pipeline.py`** — M12 needs to vary
it.

### Task 3 — Honest negative path

Zero survivors raises `NoVerifiedMatchError` (FR-022). The pipeline **never** fabricates a match,
never lowers the threshold to find one, and never falls back to "best available" below `tau`.
This is a legitimate, expected outcome and the demo shows it deliberately (M17, spec §13).

### Task 4 — Anti-cheat test

`test_candidate_independently_embedded` must **fail if the candidate-embedding call is removed**
and the pipeline still produces a match. Verify this by deleting the call, watching the test go
red, and reverting (`05` §Anti-cheat tests). A test that cannot fail is not a test.

## Technical Constraints

Reuse `face.embed` and `face.similarity` unchanged. The candidate path and the probe path must
use identical detection, alignment, and embedding code — any divergence makes the cosine
comparison meaningless.

## Interfaces / Contracts

`02` §3.7 (`ScoredCandidate`).

## Error Handling

Candidate with no detectable face → skipped, counted, logged.
Candidate fetch failure → `CandidateFetchError`, skipped, run continues (FR-053).
Zero survivors → `NoVerifiedMatchError` (FR-022).
All candidates failing to fetch → still `NoVerifiedMatchError`, not `CandidateFetchError`.

## Performance Requirements

Candidate embedding is CPU-bound at ~50ms per face and is the dominant local cost. Cache by
normalised URL within a run so the same image is never embedded twice (`06`). Never parallelise
beyond `Config.fetch_concurrency`.

## Accuracy Requirements

The recorded cosine is the real computed value, never rounded for display before storage.
`tau` is configurable and its default is documented as **unvalidated until M12**.

## Security Requirements

Candidate embeddings are biometric data derived from third-party images. They live in memory for
the run and are never persisted — only the winning candidate's *image* and the bundle's digests
survive (`09` §Privacy).

## Tests To Add

### Unit Tests
Threshold rejects at `tau - 0.01` and admits at `tau + 0.01`; ranking selects the highest;
scores are floats, never `None`.

### Integration Tests
Full loop over synthetic candidates with known embeddings produces the expected ranking.
`test_candidate_independently_embedded` — **fails if candidate embedding is removed**.

### End-to-End Tests
Marked `e2e`: real candidates from Lens, real scores.

### Regression Tests
Full suite.

### Failure Tests
`test_pipeline_no_match.py`: zero survivors raises `NoVerifiedMatchError` and **nothing is
anchored**. Candidate with no face is skipped, not scored. Every candidate failing to fetch still
yields `NoVerifiedMatchError`.

### Performance Tests
Per-candidate embedding latency; in-run cache prevents duplicate embedding.

### Accuracy Tests
Record the score distribution across real candidates — this is M12's input data.

## Commands To Run

```bash
uv run pytest tests/test_candidate_verification.py tests/test_pipeline_no_match.py -v
uv run pytest -q
uv run facechain search --image <probe>.jpg --verify-faces --threshold 0.45
```

## Acceptance Criteria

| # | Criterion | Evidence |
|---|---|---|
| 1 | Every candidate independently detected + embedded | pytest |
| 2 | Removing candidate embedding fails a test | demonstrated red, then reverted |
| 3 | Numeric cosine per candidate | pytest |
| 4 | Below-threshold rejected | pytest |
| 5 | Highest scorer selected | pytest |
| 6 | Zero survivors raises, anchors nothing | pytest |
| 7 | `tau` read from config, not hardcoded | grep |
| 8 | No-face candidate skipped, not zero-scored | pytest |

## Exit Gate

```text
MILESTONE STATUS: PASS | BLOCKED | FAILED
```

## Failure Conditions

Any of these is `FAILED`, not a warning:

- the pipeline producing a match without embedding the candidate
- a fallback to "best available" below `tau`
- a hardcoded threshold
- fabricating a match to avoid an empty result

## Rollback Strategy

Revert `pipeline.py`. M08 unaffected.

## Documentation Updates

README: how candidate verification works and why it exists — this is the project's core claim
and deserves a paragraph. `.agent-state`.

## Required Agent Report

Standard, plus the observed score distribution and explicit evidence that criterion 2 was
demonstrated red before reverting.

## Questions That Require User Input

None expected. If real candidates never clear `tau`, that is an M12 calibration input, **not**
grounds for lowering the threshold to force a demo.

## Definition of Done

Eight criteria met; the anti-cheat test proven capable of failing.
