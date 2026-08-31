# 03 — Agent Operating Contract

Every coding agent working on this project follows this contract. It is not advisory.

---

## The loop

```text
UNDERSTAND → PLAN → IMPLEMENT → TEST → MEASURE → REVIEW → PASS / BLOCK → NEXT
```

Never:

```text
UNDERSTAND → WRITE EVERYTHING → HOPE IT WORKS
```

## Mandatory sequence per milestone

1. **Read the requirements you own.** Open `01-requirements-traceability.md`, find the rows whose
   Milestone column is yours. Read those IDs in `00-requirements-intelligence.md`. Do not work
   from the milestone file alone.
2. **Inspect the repository.** What exists now, not what you assume exists.
3. **Inspect the existing implementation.** Read the modules you will touch, in full.
4. **Inspect the existing tests.** Know what currently passes before you change anything.
5. **Never overwrite working code without understanding it.** If you cannot explain why a line is
   there, do not delete it. Find out first.
6. **Write a short implementation plan** in your report before editing. Three to ten lines.
7. **Implement incrementally.** Small commits, each leaving the suite green.
8. **Run focused tests** for what you just wrote.
9. **Run regression tests** — the whole suite, not just yours.
10. **Validate every acceptance criterion** in your milestone's table, individually.
11. **Report evidence.** Paste real command output. Never describe output you did not run.
12. **Update documentation** — README, `.agent-state/current-state.md`, and any interface changes
    in `02-architecture-execution.md`.
13. **Stop if blocked by a material decision.** Use `04-question-protocol.md`. Do not guess.

## Statement typing

Every claim in an agent report carries one of these tags. Untagged claims are not accepted.

```text
FACT                    — verified by command output included in the report
ASSUMPTION              — believed true, not verified, with the cost of being wrong
IMPLEMENTATION DECISION — a reversible choice made locally, with rationale
USER DECISION REQUIRED  — material, unresolved; work stops here
RISK                    — a known way this could fail later
TEST EVIDENCE           — pasted command output
```

Example:

```text
FACT: pytest tests/test_evidence.py -> 12 passed in 0.8s (output below)
ASSUMPTION: imgbb honours the expiry parameter. Not verified live. If wrong, demo crops persist
            longer than intended — a privacy note in the README, not a correctness failure.
IMPLEMENTATION DECISION: used tuple[str, ...] for social_domains so Config stays hashable/frozen.
USER DECISION REQUIRED: AMB-05, the demo subject, is unresolved. M00 cannot run without it.
```

## Prohibitions

- **Never claim a test passes without running it.** "Should pass" is not a result.
- **Never mark a milestone PASS with a failing or skipped required test.**
- **Never weaken a test to make it pass.** If the golden hash changes, find out why. Do not
  regenerate the golden file to match new output unless you can explain the change.
- **Never silently substitute a technology.** See `31` in the master prompt: document, test the
  problem, ask.
- **Never introduce a hardcoded search result**, even temporarily, without an isolation marker
  and a deletion milestone. See `13` in the master prompt and RK-06.
- **Never let a provider error become an empty result.** (HC-17)
- **Never present cosine similarity as a percentage or a confidence.** (HC-19)
- **Never claim blockchain anchoring proves the face match is correct.** It proves the integrity
  and timestamp of a recorded claim. Nothing more.

## Handoff

At milestone end, update `.agent-state/current-state.md` per `29` in the master prompt. Never
rely on conversational memory for project-critical state. Another agent, with no history, must be
able to resume from that file alone.

## Report template

```text
## Milestone MXX — <name>

### Plan
<3-10 lines, written before implementing>

### Requirements owned
FR-###, FR-###, NFR-###

### Changes
<files created / modified, one line each>

### Test evidence
<pasted command output>

### Acceptance criteria
| Criterion | Status | Evidence |

### Statements
FACT / ASSUMPTION / IMPLEMENTATION DECISION / RISK

### Questions requiring user input
<none, or the 04-question-protocol block>

### MILESTONE STATUS: PASS | BLOCKED | FAILED
```
