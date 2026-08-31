# Milestone M12 — Accuracy Calibration

## Objective

Turn `tau = 0.45` from an assumed default into a measured operating point, and record the result.

## Why This Milestone Exists

Spec §5.4 states the default "is not treated as calibrated until that check runs." Shipping an
uncalibrated threshold while implying it was validated is the kind of overstatement that makes a
reviewer discount every other claim.

## Requirements Covered

Owns: NFR-004, NFR-005.

## Preconditions

M09 `PASS`. **AMB-01 answered** — the source and consent basis of the evaluation set.

## Inputs

`07-accuracy-engineering.md`. Score distributions recorded at M03 and M09.

## Expected Repository State Before Starting

Candidate verification green; real scores observed.

## Files To Create

```text
eval/build_set.py
eval/evaluate.py
eval/threshold_report.md
tests/test_accuracy.py
```

## Files To Modify

`README.md` — record the chosen `tau` and its observed separation (spec §5.4 requires this).

## Files That Must Not Be Modified

`face/embed.py`, `face/similarity.py` — calibration measures the system; it does not change it.

## Implementation Tasks

### Task 1 — Resolve AMB-01 first

**Do not silently scrape a face dataset.** Spec §15 says the tool is not pointed at private
individuals; assembling a labelled face set has consent implications the spec never resolves.
Ask, with the three options in `07` §AMB-01, and record which was used.

### Task 2 — Build the evaluation set

Roughly 10 same-identity pairs and 10 different-identity pairs, per spec §5.4. Small is fine and
honest; say the sample size in the report rather than implying statistical power it lacks.

### Task 3 — Measure

```text
same-identity distribution      (mean, min, max)
different-identity distribution (mean, min, max)
false positives at tau
false negatives at tau
separation between distributions
```

### Task 4 — Decide and record

Either keep 0.45 with evidence, or propose a different value with evidence. Changing the default
is an `IMPLEMENTATION DECISION` supported by data, not a preference. Record everything in
`eval/threshold_report.md` and summarise in the README.

## Technical Constraints

`tau` stays configurable. Never hardcode the new value in `pipeline.py`; change the `Config`
default only.

## Interfaces / Contracts

Unchanged. This milestone adds no interfaces.

## Error Handling

A missing or malformed evaluation image is skipped with a logged warning and excluded from the
count — never silently counted as a pass.

## Performance Requirements

None. Evaluation runs offline and is not on the critical path.

## Accuracy Requirements

The report must state sample size, distributions, and separation. If separation is poor, **say
so** — that is a finding about the operating point, not a reason to pick a threshold that makes
the demo work.

## Security Requirements

Evaluation images are biometric data. Store under `eval/data/`, git-ignored. Never commit face
images of identifiable people to a public repo without a documented basis (`09` §Privacy).

## Tests To Add

### Unit Tests
The evaluator computes distributions correctly on synthetic scores with known answers.

### Integration Tests
End-to-end evaluation over the set produces a report file.

### End-to-End Tests
None.

### Regression Tests
Full suite; changing `Config.threshold` does not break the pipeline.

### Failure Tests
Missing evaluation image is skipped and excluded, not counted.

### Performance Tests
None.

### Accuracy Tests
The whole milestone is the accuracy test.

## Commands To Run

```bash
uv run python eval/build_set.py
uv run python eval/evaluate.py --threshold 0.45
uv run pytest tests/test_accuracy.py -v
```

## Acceptance Criteria

| # | Criterion | Evidence |
|---|---|---|
| 1 | AMB-01 resolved and recorded | agent report |
| 2 | Evaluation set built, provenance documented | `eval/threshold_report.md` |
| 3 | Both distributions measured | report |
| 4 | Separation stated | report |
| 5 | `tau` kept or changed **with evidence** | report + config |
| 6 | README records the value and separation | README |
| 7 | No face images committed | `git status` |

## Exit Gate

```text
MILESTONE STATUS: PASS | BLOCKED | FAILED
```

## Failure Conditions

Choosing `tau` to make the demo produce a match. Committing identifiable face images. Claiming
calibration that was not performed.

## Rollback Strategy

Revert the `Config.threshold` default to 0.45 and state in the README that it is uncalibrated.
**This is a legitimate outcome** if the milestone is dropped for time (`10` §if-time) — the
requirement is honesty about calibration status, not calibration itself.

## Documentation Updates

README §accuracy: chosen value, separation, sample size, and the degradation caveats from spec
§15. `.agent-state`.

## Required Agent Report

Standard, plus the full distribution table.

## Questions That Require User Input

**AMB-01** — blocking. Ask before building the set.

## Definition of Done

Seven criteria met, **or** the milestone is explicitly deferred and the README states the
threshold is uncalibrated. Silence on calibration status is not an acceptable outcome.
