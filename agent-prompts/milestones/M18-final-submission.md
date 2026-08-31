# Milestone M18 — Final Submission Validation

## Objective

Run the adversarial audit, complete the validation matrix, delete throwaway code, and submit.

## Why This Milestone Exists

**There are no resubmissions.** This is the last point at which any defect can be caught, and the
one milestone whose cost of being wrong cannot be recovered.

## Requirements Covered

Owns: FR-055, FR-056, NFR-016.

## Preconditions

M16 `PASS`. M17 `PASS` with the video uploaded.

## Inputs

`99-final-audit.md`, `FINAL_VALIDATION.md`.

## Expected Repository State Before Starting

Code freeze. Video recorded.

## Files To Create

None.

## Files To Modify

`README.md` — final pass.

## Files That Must Not Be Modified

`src/`, `contracts/`, `tests/` — freeze holds. Any change here reopens M16.

## Implementation Tasks

### Task 1 — Delete the spike

Remove `spike/`. It was throwaway from the start (M00) and "not hardcoded" is explicit (HC-04,
RK-06). Verify nothing in `src/` imports it.

### Task 2 — Run the adversarial audit

Execute `99-final-audit.md` **as a fresh agent that did not write the project**. Its job is to
find requirement cheating, not to confirm the work is good.

### Task 3 — Complete the validation matrix

Every checkbox in `FINAL_VALIDATION.md`, with command, expected result, actual result, status.
No box is ticked without pasted output.

### Task 4 — Fresh-clone test (NFR-016)

Clone to a clean directory, follow the README from scratch, and confirm the suite passes. The
README is the only permitted input — if a step lives only in someone's memory, the README is
incomplete.

### Task 5 — README final pass

Required by the task (C2): what the project does, how to run it, **which blockchain**, and known
limitations. Plus the ethics statements (`09`), the accuracy caveats, the exit-code table, the
contract address with explorer link, and honest disclosure of any deferred milestone.

### Task 6 — Repository visibility

The repo is private during the build. **Flip it to public before submitting** — judges must be
able to open the link. Verify from a logged-out browser.

## Technical Constraints

No code changes. If the audit finds a defect, fixing it reopens M16 regression — budget for that
rather than patching without re-testing.

## Interfaces / Contracts

Frozen.

## Error Handling

Frozen.

## Performance Requirements

Measurements recorded in the README.

## Accuracy Requirements

The README states the threshold and whether it was calibrated. If M12 was deferred, it says so
plainly (`10` §if-time). Claiming calibration that did not happen is worse than the gap.

## Security Requirements

Final secret sweep of the working tree **and full git history** before going public. Confirm
`.env` is absent and ignored. Rotate any key that ever touched a commit.

## Tests To Add

None. Validation only.

### Unit Tests
Existing suite.

### Integration Tests
Existing suite.

### End-to-End Tests
`pytest -m e2e` one final time.

### Regression Tests
Full suite on a fresh clone.

### Failure Tests
Existing reliability suite.

### Performance Tests
Recorded.

### Accuracy Tests
Recorded.

## Commands To Run

```bash
rm -rf spike/ && grep -rn "spike" src/ tests/ || echo "spike fully removed"
uv run pytest -q --cov=src/facechain
uv run pytest -m e2e
git log -p | grep -iE "(sk-|gho_|_KEY=|0x[a-f0-9]{64})" && echo "SECRET" || echo "history clean"
cd /tmp && git clone <repo> fresh && cd fresh && uv sync && uv run pytest -q
gh repo edit <owner>/<repo> --visibility public --accept-visibility-change-consequences
```

## Acceptance Criteria

| # | Criterion | Evidence |
|---|---|---|
| 1 | `spike/` deleted, unreferenced | grep |
| 2 | Adversarial audit returns PASS or PASS WITH WARNINGS | audit report |
| 3 | Every `FINAL_VALIDATION.md` box ticked with output | matrix |
| 4 | Fresh clone reaches green from README alone | command output |
| 5 | README covers all four required topics | review |
| 6 | No secret in tree or history | scan |
| 7 | Repo public and openable logged-out | browser check |
| 8 | Video link works logged-out | browser check |
| 9 | Deferred milestones disclosed in README | review |

## Exit Gate

```text
MILESTONE STATUS: PASS | BLOCKED | FAILED
```

**Do not submit on anything but PASS.** A `BLOCKED` gate here means the submission is not ready,
and no resubmission exists to fix it later.

## Failure Conditions

Audit returns `FAIL` or `BLOCKED`. Any secret found. Fresh clone failing. Repo still private.
An overstated claim in the README.

## Rollback Strategy

None available after submission. This is why the gate is strict.

## Documentation Updates

Final README. `.agent-state/current-state.md` marked complete.

## Required Agent Report

Standard, plus the full audit report and the completed validation matrix.

## Questions That Require User Input

Final confirmation before submitting, and before flipping the repo public.

## Definition of Done

Nine criteria met, audit `PASS`, matrix complete, repo public, video live, form submitted.
