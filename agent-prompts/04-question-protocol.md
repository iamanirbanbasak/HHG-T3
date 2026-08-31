# 04 — Question Protocol

## When to ask

Ask when an unresolved issue materially affects any of:

```text
architecture          correctness        security
privacy               latency            accuracy
external service      deployment         cost
demo feasibility      interpretation of a hard requirement
```

## When not to ask

Do not ask about trivial or reversible implementation choices: naming, file splits, log wording,
which stdlib helper to use, test-fixture layout. Make the call, tag it
`IMPLEMENTATION DECISION`, and proceed.

The test: **if being wrong costs less than the round-trip of asking, decide it yourself.**

## Format

```text
## Decision Required

### Question
<one sentence, answerable>

### Why it matters
<what breaks or changes depending on the answer>

### Recommended choice
<your recommendation, and why>

### Option A
<description>

### Option B
<description>

### Consequence of each
A: <consequence>
B: <consequence>

### Blocked
<what work cannot proceed until this is answered — or "nothing, proceeding under assumption X">
```

## Known open questions

These are already identified in `00-requirements-intelligence.md` §2.6 and are **not** resolved.
An agent reaching the blocking milestone must ask rather than invent an answer.

| ID | Question | Blocks |
|---|---|---|
| AMB-01 | Source and consent basis of the threshold-calibration face set | M12 |
| AMB-02 | Base Sepolia wallet funding and key custody | M06 |
| AMB-03 | Whether an imgbb account/API key exists | **M00** |
| AMB-04 | What the demo shows if the negative-path run produces a match | M17 |
| AMB-05 | Which public figure is the demo subject | **M00** |
| AMB-06 | How post text is obtained when Lens returns only a page URL | M08 |

AMB-03 and AMB-05 block the very first milestone. Ask them before starting M00, together, in one
message.

## Proceeding under assumption

When the decision is not material and a reversible assumption is safe:

1. State the assumption explicitly, tagged `ASSUMPTION`.
2. State what it costs if wrong.
3. State where it is recorded (`.agent-state/current-state.md`).
4. Proceed.

Never bury an assumption in code without recording it.
