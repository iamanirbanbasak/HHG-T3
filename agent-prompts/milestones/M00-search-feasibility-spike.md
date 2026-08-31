# Milestone M00 — Search Feasibility Spike

> **PROPOSED DEVIATION from master §7.** The baseline milestone list has no spike milestone; Lens
> first appears at M07, four milestones deep. Master §25 requires the external search feasibility
> spike to happen early, and master §7 permits modifying the decomposition where the requirements
> justify it. M00 enforces §25 against the §7 list. Its output is an **answer**, not shipped code.

## Objective

Empirically answer three questions before any pipeline code is written:

1. Does SerpAPI Google Lens return **actual social-media post URLs** for the chosen demo subject's
   face crop — or only news, stock-photo, and aggregator pages?
2. Does the crop-hosting hop (imgbb) work end to end?
3. Do InsightFace and onnxruntime install and run on this arm64 machine?

## Why This Milestone Exists

Everything except the search leg is deterministic local work that will certainly come together.
The search leg is the only part not under our control, and R2 is unsatisfiable without it. RK-01,
RK-02, and RK-04 are all resolved here or not at all.

Discovering on Sep 5 that Lens returns nothing usable is unrecoverable with no resubmissions.
Discovering it on Sep 1 costs an afternoon.

## Requirements Covered

Validates feasibility of: FR-010, FR-012, FR-002, FR-007.
Resolves risks: RK-01, RK-02, RK-04.
**Owns no requirements.** Nothing built here ships.

## Preconditions

- **AMB-05 answered**: the demo subject is a named, specific public figure.
- **AMB-03 answered**: an imgbb API key exists, or an alternative host is chosen.
- A `SERPAPI_KEY` is available.

**Both AMB questions block this milestone. Ask them together, in one message, before starting.**

## Inputs

- One photograph of the chosen public figure, obtained from a public source.
- `SERPAPI_KEY`, `IMGBB_KEY`.

## Expected Repository State Before Starting

Repository contains `docs/` and `agent-prompts/` only. No `src/`, no `pyproject.toml`.

## Files To Create

```text
spike/probe.py              # throwaway
spike/README.md             # findings — this is the actual deliverable
spike/results/*.json        # raw provider output, committed as evidence
```

Everything under `spike/` is labelled throwaway and is **deleted at M18**.

## Files To Modify

None.

## Files That Must Not Be Modified

`docs/superpowers/specs/2026-08-31-face-chain-design.md`, and everything in `agent-prompts/`.

## Implementation Tasks

### Task 1 — Environment check

```bash
uv venv && uv pip install insightface onnxruntime opencv-python-headless numpy httpx
```

Load `buffalo_l`, run detection on the probe photo, print `det_score` and the embedding shape.
If the wheels fail on arm64, stop and report RK-04 — do not start hand-compiling dlib.

### Task 2 — Upload hop

Crop and align the face. Upload it to imgbb. Fetch the returned URL back and confirm it serves
the image bytes. Record the round-trip latency.

### Task 3 — Lens reality check

Query SerpAPI `google_lens` twice: once with the face-crop URL, once with the full-photo URL.
Dump raw JSON to `spike/results/`. Then tabulate:

```text
total candidates
unique domains
count matching the social allowlist
example social URLs (up to 5)
```

Report the crop and full-photo numbers **separately**. If the crop returns nothing but the full
photo does, that is a finding that shapes M07, not a failure.

## Technical Constraints

Throwaway quality is acceptable. No tests, no typing discipline, no error hierarchy. Do not
build abstractions here — they will be rewritten at M07 and building them twice wastes the day
this milestone exists to save.

## Interfaces / Contracts

None. Nothing here is imported by the project.

## Error Handling

Print the raw error and stop. Do not add retry logic.

## Performance Requirements

Record latency for the upload, each Lens call, and model load. These become the M13 baseline.

## Accuracy Requirements

None. No threshold is applied at this stage.

## Security Requirements

Keys come from the environment. Never paste a key into `spike/README.md` or into committed JSON —
scrub `search_metadata` blocks that echo the request URL before committing results.

## Tests To Add

### Unit Tests
None.

### Integration Tests
None.

### End-to-End Tests
The spike *is* the end-to-end probe.

### Regression Tests
None.

### Failure Tests
None.

### Performance Tests
Latency recorded, not asserted.

### Accuracy Tests
None.

## Commands To Run

```bash
uv run python spike/probe.py --image <subject>.jpg --mode env
uv run python spike/probe.py --image <subject>.jpg --mode upload
uv run python spike/probe.py --image <subject>.jpg --mode lens
```

## Acceptance Criteria

| # | Criterion | Evidence |
|---|---|---|
| 1 | InsightFace loads and detects on arm64 | printed `det_score`, embedding shape `(512,)` |
| 2 | imgbb returns a URL that serves the image | HTTP 200 and matching byte length |
| 3 | Lens returns >= 1 URL on the social allowlist | tabulated counts + example URLs |
| 4 | Raw provider output committed | `spike/results/*.json` |
| 5 | Findings written up | `spike/README.md` |

## Exit Gate

```text
MILESTONE STATUS: PASS      — criterion 3 met; M01 may start
MILESTONE STATUS: BLOCKED   — criterion 3 not met; a USER DECISION is required before proceeding
MILESTONE STATUS: FAILED    — criterion 1 or 2 not met; the stack itself needs a decision
```

**Do not proceed to M01 on a BLOCKED gate.** Report options: a different subject, a second
provider (TinEye), a widened allowlist, or a documented deviation.

## Failure Conditions

- Zero social URLs from **both** queries → RK-01 realised, escalate immediately.
- imgbb unusable → RK-02 realised, propose alternatives (catbox, 0x0.st) and ask.
- Wheels fail on arm64 → RK-04 realised. Substituting a different face library is a **material
  deviation**; ask per master §31, do not silently swap.

## Rollback Strategy

Delete `spike/`. Nothing else was touched.

## Documentation Updates

`spike/README.md` with findings. Create `.agent-state/current-state.md` and record the outcome,
the subject chosen, and observed Lens behaviour.

## Required Agent Report

Per `03-agent-operating-contract.md`, plus the candidate-domain table and, if BLOCKED, a
`04-question-protocol.md` decision block.

## Questions That Require User Input

- **AMB-05** — which public figure? Blocks the milestone.
- **AMB-03** — is there an imgbb key? Blocks the milestone.
- If criterion 3 fails: which fallback?

## Definition of Done

Criteria 1–5 met, findings written, `.agent-state/current-state.md` created, exit gate declared,
and — if BLOCKED — the user has answered before M01 begins.
