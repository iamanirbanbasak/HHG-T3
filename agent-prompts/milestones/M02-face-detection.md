# Milestone M02 — Face Detection

## Objective

Implement `face.detect`: load an image, detect faces with SCRFD, select the probe, align to a
112x112 crop.

## Why This Milestone Exists

HC-01 requires that face detection actually occurs. This is where that becomes true. Every
downstream stage consumes `DetectedFace`.

## Requirements Covered

Owns: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006.

## Preconditions

M01 `PASS`. M00 confirmed InsightFace works on this machine (RK-04 closed).

## Inputs

`02` §3.1. Test fixture images: one clear single face, one two-face image, one with no face, one
malformed file.

## Expected Repository State Before Starting

`src/facechain/{config,errors}.py` exist; suite green.

## Files To Create

```text
src/facechain/face/detect.py
src/facechain/face/models.py       # lazy singleton loader for buffalo_l
tests/test_detect.py
tests/fixtures/face_single.jpg
tests/fixtures/face_double.jpg
tests/fixtures/face_none.jpg
tests/fixtures/malformed.jpg
```

## Files To Modify

`src/facechain/face/__init__.py`.

## Files That Must Not Be Modified

`config.py`, `errors.py`, `agent-prompts/`, `docs/`.

## Implementation Tasks

### Task 1 — Lazy model loader

`models.py` loads the `buffalo_l` pack once per process and caches it (NFR-002). Never load at
import time. Document the ~300MB first-run download (RK-09).

### Task 2 — `load_image` and `detect_faces`

Signatures verbatim from `02` §3.1. Return detections sorted by `det_score` **descending**, so
`[0]` is always the probe (FR-003). Zero detections raises `NoFaceDetectedError` (FR-005).

### Task 3 — Alignment

Standard ArcFace 5-point similarity transform to 112x112. Alignment must be **deterministic**:
the same input yields byte-identical output. The evidence chain depends on this.

## Technical Constraints

Use InsightFace's SCRFD as specified. Do not substitute another detector — that is a material
deviation requiring a question (master §31).

## Interfaces / Contracts

`02` §3.1, exactly. `DetectedFace` is frozen.

## Error Handling

- unreadable/malformed file → `FaceChainError` naming the path
- zero faces → `NoFaceDetectedError`
- **never fabricate a detection or a synthetic embedding** to keep a run alive

## Performance Requirements

Detection under ~200ms per image after warm-up. Model loads exactly once — assert it.

## Accuracy Requirements

`det_score > 0.5` on the clear single-face fixture. No threshold tuning happens here.

## Security Requirements

Bound decoded image dimensions; reject absurdly large images before decode (NFR-012).

## Tests To Add

### Unit Tests
JPEG and PNG load; detection on the single-face fixture; probe is highest score on the two-face
fixture; `faces_detected == 2` recorded; blank image raises `NoFaceDetectedError`; aligned output
is `(112,112,3)` and byte-stable across two calls.

### Integration Tests
Model loads once across multiple detections.

### End-to-End Tests
None.

### Regression Tests
Full suite.

### Failure Tests
Malformed file; zero-byte file; a non-image file with a `.jpg` extension.

### Performance Tests
Warm detection latency recorded.

### Accuracy Tests
`det_score` above 0.5 on the clear fixture.

## Commands To Run

```bash
uv run pytest tests/test_detect.py -v
uv run pytest -q
uv run facechain scan --image tests/fixtures/face_single.jpg
```

## Acceptance Criteria

| # | Criterion | Evidence |
|---|---|---|
| 1 | Detects a real face | pytest |
| 2 | Probe selection deterministic | pytest |
| 3 | `NoFaceDetectedError` on empty | pytest |
| 4 | Aligned crop is 112x112 and stable | pytest |
| 5 | Multi-face count recorded | pytest |
| 6 | Model loads once | pytest |

## Exit Gate

```text
MILESTONE STATUS: PASS | BLOCKED | FAILED
```

## Failure Conditions

Non-deterministic alignment (breaks the whole evidence chain); any fabricated detection.

## Rollback Strategy

Revert `face/`; M01 is unaffected.

## Documentation Updates

README: first-run model download note. `.agent-state`.

## Required Agent Report

Standard, plus measured detection latency.

## Questions That Require User Input

None expected.

## Definition of Done

Six criteria met; alignment proven deterministic.
