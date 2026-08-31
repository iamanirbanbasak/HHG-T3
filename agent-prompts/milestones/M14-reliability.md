# Milestone M14 — Reliability & Failure Handling

## Objective

Test all eighteen failure modes from `08-reliability-engineering.md`.

## Why This Milestone Exists

Live demos fail on the paths nobody tested. More importantly, HC-17 — provider errors never
reading as "no results" — is a correctness property, not a robustness nicety, and it needs a test
that proves the distinction holds.

## Requirements Covered

Owns: NFR-006.
Re-validates: FR-052, FR-053.

## Preconditions

M10 `PASS`.

## Inputs

`08-reliability-engineering.md`, all eighteen rows.

## Expected Repository State Before Starting

Full pipeline green on the happy path.

## Files To Create

```text
tests/reliability/__init__.py
tests/reliability/test_face_failures.py
tests/reliability/test_provider_failures.py
tests/reliability/test_candidate_failures.py
tests/reliability/test_chain_failures.py
tests/reliability/test_artifact_failures.py
```

## Files To Modify

Any module whose failure handling proves inadequate under test.

## Files That Must Not Be Modified

`contracts/` — frozen.

## Implementation Tasks

### Task 1 — All eighteen rows

One test per row of `08`. No row is skipped as "unlikely" — row 7 (invalid API key) and row 9
(candidate 403) are the two most likely to occur live.

### Task 2 — The distinction, proven

Write two tests that differ **only** in the mocked response:

```text
provider returns 500        →  SearchProviderError   →  exit 3
provider returns empty 200  →  []  →  NoVerifiedMatch →  exit 4
```

That pairing is the proof of HC-17. A single test cannot demonstrate a distinction.

### Task 3 — Partial-failure semantics

One candidate failing skips one candidate. **Every** candidate failing yields
`NoVerifiedMatchError`, not `CandidateFetchError` — the run completed and found nothing
verifiable, which is a different statement from "a fetch broke".

### Task 4 — No silent handling

Audit every `except` in `src/`. Each either logs with a stack trace and re-raises, or converts to
a typed domain error carrying context. A bare `except:` is a review failure. No exception is
caught to make a demo look smoother.

## Technical Constraints

All failures simulated with mocks. No test may depend on a real service being down.

## Interfaces / Contracts

Unchanged.

## Error Handling

This milestone *is* error handling. Every raised error carries actionable context: which file,
which URL, which status — never the API key (row 7).

## Performance Requirements

Timeouts must actually fire. Assert that a hung provider fails at the configured timeout rather
than hanging the run.

## Accuracy Requirements

A candidate with no detectable face is skipped, never scored zero — scoring it zero would
pollute the M12 distributions with non-comparisons.

## Security Requirements

Row 7 is a security test as much as a reliability one: an invalid key must produce an error whose
message **never contains the key**.

## Tests To Add

### Unit Tests
Rows 1, 2, 3 (face); rows 4–7 (provider).

### Integration Tests
Rows 9–12 (candidates); rows 13–15 (chain, on `eth-tester`).

### End-to-End Tests
None — all simulated.

### Regression Tests
Full suite.

### Failure Tests
All eighteen rows. This section is the milestone.

### Performance Tests
Timeouts fire at the configured value.

### Accuracy Tests
No-face candidate skipped rather than zero-scored.

## Commands To Run

```bash
uv run pytest tests/reliability/ -v
uv run pytest -q
grep -rn "except:" src/ && echo "BARE EXCEPT FOUND — fix" || echo "no bare except"
grep -rn "except Exception" src/
```

## Acceptance Criteria

| # | Criterion | Evidence |
|---|---|---|
| 1 | All eighteen rows tested | pytest |
| 2 | Provider-error vs empty proven by a paired test | pytest |
| 3 | One failure skips one candidate | pytest |
| 4 | All candidates failing → `NoVerifiedMatchError` | pytest |
| 5 | No bare `except:` in `src/` | grep |
| 6 | API key absent from all error messages | pytest |
| 7 | Timeouts fire | pytest |

## Exit Gate

```text
MILESTONE STATUS: PASS | BLOCKED | FAILED
```

## Failure Conditions

Any provider error reachable as an empty result. A bare `except:`. A key in an error message.

## Rollback Strategy

Reliability tests are additive; they do not need rollback. Fixes they prompt are individually
revertible.

## Documentation Updates

README: known failure modes and what the user sees for each. `.agent-state`.

## Required Agent Report

Standard, plus the eighteen-row status table.

## Questions That Require User Input

None expected.

## Definition of Done

Seven criteria met. If deferred for time (`10` §if-time), rows 7, 8, 9, 12, 13 are the
non-negotiable subset and the rest are documented as untested.
