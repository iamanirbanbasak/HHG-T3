# Milestone M07 — Search Upload + Lens Integration

## Objective

Implement `search.uploader` and `search.lens`. Issue two genuine reverse-image-search queries:
the aligned face crop (primary) and the full photo (recall widening).

## Why This Milestone Exists

HC-05 requires a genuine reverse-image-search operation. This is where the project stops being
local computation and starts making real external claims.

## Requirements Covered

Owns: FR-010, FR-011, FR-012, FR-013, FR-052.

## Preconditions

M00 `PASS` (Lens returns social URLs for the subject). M01, M03 `PASS`.
**AMB-03 resolved**: imgbb key exists or an alternative host is chosen.

## Inputs

M00's findings in `spike/README.md` — the observed Lens response shape drives the parser.
`02` §3.4, §3.5.

## Expected Repository State Before Starting

Face pipeline works through embedding. Suite green.

## Files To Create

```text
src/facechain/search/uploader.py
src/facechain/search/lens.py
tests/test_uploader.py
tests/test_lens.py
tests/test_search_error.py
tests/fixtures/lens_response.json        # a real captured response, clearly marked as a test fixture
```

## Files To Modify

`src/facechain/search/__init__.py`, `.env.example`.

## Files That Must Not Be Modified

`face/`, `evidence.py`, `chain/`.

## Implementation Tasks

### Task 1 — `uploader.upload`

POST the image to imgbb, set a one-day expiry (FR-011), return the public HTTPS URL. Non-2xx
raises `SearchProviderError`.

This hop exists because Google Lens accepts a URL, not raw bytes (RK-02). It is the moving part
most likely to be underestimated.

### Task 2 — `lens.search`

Call SerpAPI `google_lens` with the image URL. Parse visual matches into `Candidate` objects per
`02` §3.5. Parse defensively — the fixture from M00 is one observed shape, not a guarantee.

### Task 3 — The distinction that must not blur

```text
provider failure  →  raises SearchProviderError
no matches found  →  returns []
```

**These are different outcomes and must never be conflated** (FR-052, HC-17). A broken API key
must not look like a legitimate negative result. Two tests differing only in the mocked response
prove the distinction.

### Task 4 — Delete the dev stub

If M02–M05 used a stubbed candidate to develop against, **delete it now**. RK-06: a surviving
stub violates HC-04, and there are no resubmissions. Record the deletion in the agent report.

## Technical Constraints

The **aligned face crop is the primary query** (FR-012). The embedding vector itself is never
sent to any provider — Lens receives an image, never 512 floats. The full-photo query exists to
widen recall (FR-013), never to bypass face verification (`02` §5, master §12).

## Interfaces / Contracts

`02` §3.4, §3.5, exactly.

## Error Handling

Timeout, 4xx, 5xx, malformed body → `SearchProviderError` naming the status. **The API key never
appears in the message** (`08` row 7). Empty but valid response → `[]`.

## Performance Requirements

Explicit connect and read timeouts. Record upload and per-query Lens latency. Exactly two Lens
calls per run — assert it (FR-013).

## Accuracy Requirements

None here. Face verification at M09 is the arbiter; this milestone only produces candidates.

## Security Requirements

Keys from `Config` only, never logged (NFR-011). Uploaded crops expire in one day (`09`
§Privacy). Committed fixtures must have `search_metadata` scrubbed of any URL echoing the key.

## Tests To Add

### Unit Tests
Upload returns a URL and sets expiry; Lens parses the captured fixture into `Candidate` objects;
malformed JSON raises rather than returning `[]`.

### Integration Tests
Two queries issued per run; the crop URL is the primary query; **no 512-float payload is ever
sent to a provider** (`test_crop_is_the_query`).

### End-to-End Tests
Marked `e2e`: one real crop → real imgbb → real Lens → at least one candidate.

### Regression Tests
Full offline suite green with no API keys set.

### Failure Tests
`test_search_error.py`: 500 raises; 401 raises; timeout raises; empty-but-valid returns `[]`. The
500 and empty cases differ only in the mocked response — that pairing is the point.

### Performance Tests
Upload and Lens latency recorded.

### Accuracy Tests
None.

## Commands To Run

```bash
uv run pytest tests/test_uploader.py tests/test_lens.py tests/test_search_error.py -v
uv run pytest -q
uv run pytest -m e2e tests/test_lens.py -v
uv run facechain search --image tests/fixtures/face_single.jpg
grep -rn "instagram.com\|twitter.com\|x.com" src/ || echo "no hardcoded social URL in src"
```

## Acceptance Criteria

| # | Criterion | Evidence |
|---|---|---|
| 1 | Upload returns a working public URL | e2e output |
| 2 | Lens returns parsed candidates | pytest + e2e |
| 3 | Crop is the primary query | pytest |
| 4 | Exactly two queries per run | pytest |
| 5 | Provider error ≠ empty result | two paired tests |
| 6 | Key never logged | captured output |
| 7 | Dev stub deleted | `git diff` + grep |

## Exit Gate

```text
MILESTONE STATUS: PASS | BLOCKED | FAILED
```

## Failure Conditions

A provider error returning `[]`. A hardcoded candidate URL in `src/`. The embedding being sent to
a provider. A surviving dev stub.

## Rollback Strategy

Revert `search/`. The face pipeline and chain layer are unaffected.

## Documentation Updates

README: which search provider, why, the imgbb hop and its rationale, rate limits. `.agent-state`.

## Required Agent Report

Standard, plus candidate counts per query type and explicit confirmation the stub is deleted.

## Questions That Require User Input

**AMB-03** if unresolved. If Lens recall proves too thin, adding a second provider is a material
deviation — ask per master §31.

## Definition of Done

Seven criteria met; provider-vs-empty distinction proven by paired tests; stub gone.
