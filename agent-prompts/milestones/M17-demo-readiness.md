# Milestone M17 — Demo Readiness & Recording

## Objective

Record the screen capture showing the genuine end-to-end path, including the tamper demonstration
and the negative path.

## Why This Milestone Exists

The recording is a graded submission artifact (S1). Master §23 requires the demo to exercise the
**actual** path with no mocked services.

## Requirements Covered

Validates end to end: HC-01 through HC-19. Owns no new requirements.

## Preconditions

M11 `PASS`. M06 `PASS` or the `local` fallback rehearsed (RK-05).

## Inputs

Master §23 (the required path), §24 (the negative path). Spec §13 (demo subjects).

## Expected Repository State Before Starting

Submission-ready. No `e2e` failures.

## Files To Create

```text
demo/script.md              # the run order for the recording
demo/rehearsal-notes.md
```

## Files To Modify

None. **Code freeze.** A change made on recording day is a change that was never regression-tested.

## Files That Must Not Be Modified

All of `src/`, `contracts/`, `tests/`.

## Implementation Tasks

### Task 1 — Rehearse before recording

Run the full path once, end to end, before the real take. A rehearsal surfaces missing model
caches (RK-09), expired uploads, and empty faucet wallets (RK-05) while there is still time.

Pre-warm the `buffalo_l` models. A 300MB download mid-recording is a retake.

### Task 2 — The real path, no substitutions

```text
real input photo
→ real face detection
→ real embedding
→ real search provider (SerpAPI Lens)
→ real candidate retrieval
→ real candidate face verification
→ real evidence bundle
→ real blockchain anchor
→ real blockchain read
→ real local recomputation
→ successful verification
→ tamper demonstration
```

**No mocked services in the final recording** (master §23). If an external dependency prevents
the demo, report it as a **blocker** — do not substitute a mock and present it as live.

### Task 3 — The tamper demonstration

`verify --tamper` is the most convincing twenty seconds available. Show the on-chain hash, the
recomputed hash, and the MISMATCH. Then show the original artifacts are unchanged.

### Task 4 — The negative path (master §24)

Run the secondary self-face pass on camera. The expected outcome is no match or a low-confidence
rejection, and showing it proves the threshold does real work and that the system does not force
every input to produce a result.

**AMB-04**: if the self-face pass unexpectedly *produces* a match, show it honestly with its real
score. Do not re-shoot until you get the expected outcome — that would be selecting evidence,
which is precisely what the project claims not to do.

### Task 5 — Explain the limitation on camera

State plainly that the chain proves *when a claim was recorded*, not that the claim is true.
Ten seconds, and it distinguishes the submission from every other one that conflates the two.

## Technical Constraints

Terminal at a legible font size. Assume compressed video at 1x.

## Interfaces / Contracts

Unchanged — code freeze.

## Error Handling

If a live failure occurs mid-recording, show it and narrate it. A demonstrated real failure with
a clear error message is more credible than a suspiciously smooth run.

## Performance Requirements

Pre-warm models so latency reflects steady state. Note the cold-start cost verbally.

## Accuracy Requirements

Show the real cosine and the threshold together. **Never say "percent" or "confidence"** on
camera (HC-19).

## Security Requirements

**Scrub the terminal of secrets before recording.** No `.env` contents, no key echoed by a shell
command, no key in scrollback. Check the scrollback before starting — this is the single most
likely way to leak a key in a graded submission.

## Tests To Add

### Unit Tests
None — code freeze.

### Integration Tests
None.

### End-to-End Tests
`uv run pytest -m e2e` must be green before recording.

### Regression Tests
Full suite green before recording.

### Failure Tests
None.

### Performance Tests
Note observed live latencies in `demo/rehearsal-notes.md`.

### Accuracy Tests
None.

## Commands To Run

```bash
uv run pytest -q && uv run pytest -m e2e
uv run facechain run --image <subject>.jpg --network base-sepolia
uv run facechain verify --record-id <N> --network base-sepolia
uv run facechain verify --record-id <N> --network base-sepolia --tamper
uv run facechain run --image <self>.jpg --network base-sepolia     # negative path
```

## Acceptance Criteria

| # | Criterion | Evidence |
|---|---|---|
| 1 | Rehearsal completed before the take | rehearsal notes |
| 2 | Full real path recorded, no mocks | video |
| 3 | Real social post URL visible | video |
| 4 | Real cosine and threshold shown | video |
| 5 | On-chain anchor with explorer link | video |
| 6 | Verify MATCH shown | video |
| 7 | Tamper MISMATCH shown | video |
| 8 | Negative path shown honestly | video |
| 9 | No secret visible at any point | video review |
| 10 | Video uploaded, link tested | working URL |

## Exit Gate

```text
MILESTONE STATUS: PASS | BLOCKED | FAILED
```

## Failure Conditions

Any mocked service presented as live. Any secret visible. A re-shot negative path to obtain a
more convenient outcome.

## Rollback Strategy

Re-record. Never edit the video to hide a failure — the task explicitly permits an unedited plain
recording, and editing invites doubt about what was cut.

## Documentation Updates

README: link to the recording. `.agent-state`.

## Required Agent Report

Standard, plus the video URL and confirmation the link works when logged out.

## Questions That Require User Input

**AMB-04** if the negative path produces an unexpected match.

## Definition of Done

Ten criteria met; video uploaded and the link verified from a logged-out browser.
