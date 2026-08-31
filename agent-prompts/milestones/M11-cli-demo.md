# Milestone M11 — CLI & Demo Experience

## Objective

Complete the six-command CLI with Rich output legible in a screen recording.

## Why This Milestone Exists

The CLI is the only UI (HC-18, NG-01) and the screen recording is a graded submission artifact.
Output that is technically correct but illegible on video loses marks that the engineering
already earned.

## Requirements Covered

Owns: FR-041, FR-042, FR-049, FR-050, FR-051, NFR-005, NFR-014.

## Preconditions

M10 `PASS`.

## Inputs

Master §22 field list. `02` §3.10.

## Expected Repository State Before Starting

Pipeline runs end to end; verify and tamper work.

## Files To Create

```text
tests/test_cli.py
```

## Files To Modify

```text
src/facechain/cli.py
README.md
```

## Files That Must Not Be Modified

`pipeline.py`, `evidence.py`, `chain/` — the CLI presents; it does not compute. If the CLI needs
business logic, it belongs one layer down.

## Implementation Tasks

### Task 1 — Six commands

```text
scan     — detect + embed, show bbox, det_score, embedding digest
search   — scan + Lens + filter, show candidate table
anchor   — build bundle, hash, anchor, show tx and record id
verify   — on-chain read + local recompute, show both hashes
run      — all stages with Rich progress
deploy   — deploy the contract to the selected network
```

Each runs standalone so one leg can be re-recorded without repeating the whole pipeline
(NFR-014).

### Task 2 — Demo-legible output

Every field from master §22 must be visible: current stage, candidate count, face verification
score, threshold, selected match, evidence hash, network, transaction hash, verification result.

Use Rich panels and tables. Large monospace hashes, truncated with the full value available.
Colour: green MATCH, red MISMATCH. Assume the viewer is watching a compressed video at 1x.

### Task 3 — Language discipline

```text
CORRECT:   cosine similarity 0.7123 (threshold 0.45)
WRONG:     71.23% confidence
WRONG:     71% match
```

Never render similarity as a percentage anywhere (FR-051, NFR-005, HC-19). The audit sweep greps
for a `%` adjacent to a similarity value.

### Task 4 — Exit codes

Per `02` §7: 0 success, 1 mismatch, 2 no face, 3 provider error, 4 no verified match, 5 chain
error. Documented in the README so a reviewer can script against them.

## Technical Constraints

Typer + Rich. `cli.py` is the only module that constructs `Config` (FR-054).

## Interfaces / Contracts

`load_config` then pass the frozen `Config` down. No module below reads the environment.

## Error Handling

Every typed error maps to a distinct exit code and a human-readable Rich panel. A traceback must
never be the primary output of an expected failure — `NoVerifiedMatchError` is a legitimate
outcome and should read as one, not as a crash.

## Performance Requirements

`--help` under 200ms: no model loading at import (NFR-002). Progress output must not add
measurable latency to the stages it reports on.

## Accuracy Requirements

Display the real cosine to four decimals. Never round before storing.

## Security Requirements

No secret ever rendered, including in verbose or debug modes (NFR-011). `Config` repr is already
redacted from M01 — verify the CLI does not bypass it.

## Tests To Add

### Unit Tests
Each command's `--help` returns 0. Exit-code mapping per error type.

### Integration Tests
`test_all_commands_invocable`; `test_verify_output` asserts both hashes, block, and network are
present in stdout; `test_output_fields_present` asserts all nine master §22 fields.

### End-to-End Tests
Marked `e2e`: full `run` against real services, captured for the recording rehearsal.

### Regression Tests
Full suite.

### Failure Tests
Each error type renders a readable panel, not a traceback.

### Performance Tests
`--help` latency asserted.

### Accuracy Tests
No `%` adjacent to any similarity value — grep assertion in the test suite, not only in the audit.

## Commands To Run

```bash
uv run facechain --help
uv run facechain scan --image <probe>.jpg
uv run facechain search --image <probe>.jpg
uv run facechain run --image <probe>.jpg --network local
uv run facechain verify --record-id 0 --network local
uv run facechain verify --record-id 0 --network local --tamper
uv run pytest tests/test_cli.py -v
```

## Acceptance Criteria

| # | Criterion | Evidence |
|---|---|---|
| 1 | Six commands, each standalone | pytest |
| 2 | All nine required fields displayed | captured stdout |
| 3 | No similarity rendered as a percentage | grep + pytest |
| 4 | Exit codes correct and documented | pytest + README |
| 5 | Errors render as panels, not tracebacks | pytest |
| 6 | `--help` under 200ms | pytest |
| 7 | No secret in any output mode | pytest |

## Exit Gate

```text
MILESTONE STATUS: PASS | BLOCKED | FAILED
```

## Failure Conditions

Any percentage rendering of similarity. A secret in verbose output. Business logic in `cli.py`.

## Rollback Strategy

Revert `cli.py`. The pipeline remains usable via its Python API.

## Documentation Updates

README: every command with example output, and the exit-code table. `.agent-state`.

## Required Agent Report

Standard, plus a captured `run` and `verify --tamper` transcript.

## Questions That Require User Input

None expected.

## Definition of Done

Seven criteria met; output rehearsed at video resolution and confirmed legible.
