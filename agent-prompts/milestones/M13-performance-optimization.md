# Milestone M13 — Performance Optimization

## Objective

Measure the critical path, then optimise only what measurement justifies.

## Why This Milestone Exists

Master §18 requires performance to be measured rather than guessed. This milestone exists to
produce numbers; optimisation is what the numbers may or may not justify.

**This is the first milestone to drop under deadline pressure (RK-10, `10` §if-time).** If
dropped, measurement still happens — only optimisation is deferred.

## Requirements Covered

Owns: NFR-001, NFR-002, NFR-003.

## Preconditions

M10 `PASS` — there must be a complete path to measure.

## Inputs

`06-performance-engineering.md`. Baselines recorded at M00, M02, M03, M05, M06.

## Expected Repository State Before Starting

Full pipeline runs end to end.

## Files To Create

```text
bench/run_bench.py
bench/latest.json
tests/test_perf.py
```

## Files To Modify

Only modules whose measurements justify a change.

## Files That Must Not Be Modified

`evidence.py` — hashing is negligible; "optimising" it risks determinism for nothing.
`contracts/` — frozen.

## Implementation Tasks

### Task 1 — Measure first

Instrument all ten stages from `06`. Run against mocked providers so numbers are comparable run
to run. Emit p50/p95 where sample size supports it; with fewer than ~20 samples report p50 and
max and say so.

### Task 2 — Optimise only what the data justifies

Permitted: model warm-up and reuse, connection pooling, explicit timeouts, bounded concurrent
fetching, image size limits, in-run embedding cache, avoiding redundant serialisation.

Every change carries a before/after number in the report. **An optimisation without a measurement
is not an optimisation; it is an unreviewed change to working code.**

### Task 3 — Respect the forbidden list

Never: unbounded concurrency (NFR-003); removing verification (HC-03); reducing accuracy without
documenting the trade-off; lowering candidate count below what the threshold needs.

Deleting the candidate-embedding step makes the run much faster and the project fraudulent. If a
profiler points there, the profiler is right about the cost and wrong about the remedy.

## Technical Constraints

Concurrency capped by `Config.fetch_concurrency`. Optimisation must not change any output — the
golden hash is unchanged by definition.

## Interfaces / Contracts

Unchanged. If an optimisation requires an interface change, it needs `02` updated first.

## Error Handling

Unchanged. Never remove a try/except for speed.

## Performance Requirements

Produce `bench/latest.json` with per-stage p50 and p95. Characterise the critical path. State
which stage dominates and why.

## Accuracy Requirements

Zero accuracy change. Assert the golden hash and a fixed-input cosine are identical before and
after every optimisation.

## Security Requirements

Timeouts and size caps are security controls (`09`), not performance knobs. Never relax them for
throughput.

## Tests To Add

### Unit Tests
`test_single_model_load` — the loader is invoked once per process.

### Integration Tests
In-run cache prevents duplicate embedding of the same candidate.

### End-to-End Tests
Marked `e2e`: `--live` benchmark for the M17 rehearsal.

### Regression Tests
Full suite; golden hash unchanged.

### Failure Tests
Concurrency cap holds under a burst of candidates.

### Performance Tests
`test_concurrency_cap`; per-stage latency recorded to `bench/latest.json`.

### Accuracy Tests
Fixed-input cosine identical before and after optimisation.

## Commands To Run

```bash
uv run python bench/run_bench.py
uv run python bench/run_bench.py --live      # M17 rehearsal only
uv run pytest tests/test_perf.py -v
uv run pytest -q
```

## Acceptance Criteria

| # | Criterion | Evidence |
|---|---|---|
| 1 | All ten stages measured | `bench/latest.json` |
| 2 | Critical path characterised | report |
| 3 | Every optimisation has before/after | report |
| 4 | Model loads once | pytest |
| 5 | Concurrency bounded | pytest |
| 6 | Golden hash unchanged | pytest |
| 7 | No verification removed | code review |

## Exit Gate

```text
MILESTONE STATUS: PASS | BLOCKED | FAILED
```

"Measured, no optimisation needed" is a valid `PASS`.

## Failure Conditions

Any optimisation that changes output. Unbounded concurrency. Relaxed timeouts or size caps.

## Rollback Strategy

Revert the optimisation commits; keep `bench/`. Measurement is the durable value here.

## Documentation Updates

README: measured latencies. `.agent-state`.

## Required Agent Report

Standard, plus the full stage table and before/after for each change.

## Questions That Require User Input

None expected.

## Definition of Done

Seven criteria met, or the milestone deferred with measurements recorded.
