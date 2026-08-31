# Milestone M16 — Full Integration & Regression

## Objective

Run the complete suite offline, reach 80% coverage, verify the import graph, and prove every
anti-cheat test can actually fail.

## Why This Milestone Exists

Milestones passed individually. This one proves they still pass together, and — more importantly
— that the tests guarding the project's central claims are capable of going red.

## Requirements Covered

Owns: NFR-009, NFR-013, NFR-017.

## Preconditions

M11 `PASS`. M14, M15 complete or explicitly deferred.

## Inputs

`05-testing-strategy.md` §Anti-cheat tests. `02` §2 (dependency direction).

## Expected Repository State Before Starting

All must-ship milestones green.

## Files To Create

```text
tests/test_no_hardcoding.py
tests/test_import_graph.py
```

## Files To Modify

Any module whose coverage is short, or which violates the import graph.

## Files That Must Not Be Modified

`contracts/` — frozen.

## Implementation Tasks

### Task 1 — Offline suite

Full run with networking disabled. Everything except `e2e`-marked tests must pass (NFR-009). A
test that needs the network and is not marked `e2e` is a bug in the test.

### Task 2 — Coverage

`pytest --cov`, target 80% (NFR-017). If short, add tests for the uncovered paths — do not lower
the target silently. If the target is missed, **state the actual number** in the README rather
than claiming 80%.

### Task 3 — Import graph

`test_import_graph.py` asserts the dependency direction from `02` §2: `config` and `errors`
import nothing from the project; `face.*`, `search.*`, `evidence`, `chain.*` never import
`pipeline` or `cli`; `evidence` never imports `face.*` or `search.*`; `os.environ` appears only
in `config.py`.

### Task 4 — Prove the anti-cheat tests can fail

For each of the eight tests in `05` §Anti-cheat tests: introduce the shortcut it guards against,
confirm the test goes **red**, revert, confirm green. Record each in the report.

**A test that cannot fail is not a test.** This task is the difference between having anti-cheat
tests and appearing to have them.

### Task 5 — No hardcoding sweep

`test_no_hardcoding.py`: no social-media URL literal reachable from the production path; no
fixture used as live search output; the M00 `spike/` directory not imported by `src/`.

## Technical Constraints

The offline run must be genuinely offline — block networking rather than trusting that no test
reaches out.

## Interfaces / Contracts

Unchanged. Violations found here are fixed in the offending module, not by relaxing `02`.

## Error Handling

Unchanged.

## Performance Requirements

Full suite under 5 minutes, or parallelised. A slow suite gets run less often.

## Accuracy Requirements

Golden hash unchanged from M04.

## Security Requirements

Re-run the M15 checks as regression.

## Tests To Add

### Unit Tests
Import-graph assertions.

### Integration Tests
Full pipeline on `eth-tester` with mocked providers.

### End-to-End Tests
Deselected here; M17 owns the live path.

### Regression Tests
The entire suite, offline.

### Failure Tests
All eighteen `08` rows still pass.

### Performance Tests
Suite runtime recorded.

### Accuracy Tests
Golden hash and fixed-input cosine unchanged.

## Commands To Run

```bash
uv run pytest -q --cov=src/facechain --cov-report=term-missing
uv run pytest tests/test_import_graph.py tests/test_no_hardcoding.py -v
uv run ruff check .
grep -rn "os.environ" src/ | grep -v config.py && echo "ENV LEAK" || echo "env access clean"
```

## Acceptance Criteria

| # | Criterion | Evidence |
|---|---|---|
| 1 | Full suite green offline | pytest output |
| 2 | Coverage >= 80%, or actual number stated | coverage report |
| 3 | Import graph clean | pytest |
| 4 | All eight anti-cheat tests demonstrated red then green | agent report |
| 5 | No hardcoded result reachable | pytest + grep |
| 6 | Golden hash unchanged | pytest |
| 7 | `ruff` clean | command output |

## Exit Gate

```text
MILESTONE STATUS: PASS | BLOCKED | FAILED
```

## Failure Conditions

Any anti-cheat test that **cannot** be made to fail — that means it is not testing what it
claims. A network-dependent test not marked `e2e`. A hardcoded result reachable from production.

## Rollback Strategy

Regression findings are fixed forward, not rolled back.

## Documentation Updates

README: how to run the suite, actual coverage number. `.agent-state`.

## Required Agent Report

Standard, plus the eight-row anti-cheat red/green table and the coverage number.

## Questions That Require User Input

If coverage cannot reach 80% in the time remaining: confirm shipping with the actual number
stated rather than silently lowering the target.

## Definition of Done

Seven criteria met; every anti-cheat test proven capable of failing.
