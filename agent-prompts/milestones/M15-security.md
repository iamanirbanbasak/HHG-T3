# Milestone M15 — Security & Privacy Hardening

## Objective

Verify every control in `09-security-hardening.md`: secrets, untrusted input, privacy, and the
ethical statements the README must carry.

## Why This Milestone Exists

The repo will be public and holds a funded testnet key. It also computes and stores biometric
data. Both deserve deliberate treatment rather than an assumption that nothing leaked.

## Requirements Covered

Owns: NFR-011, NFR-012.
Re-validates: FR-051, FR-056.

## Preconditions

M10 `PASS`.

## Inputs

`09-security-hardening.md`. Spec §15.

## Expected Repository State Before Starting

Full pipeline green.

## Files To Create

```text
tests/test_security.py
SECURITY.md
```

## Files To Modify

`README.md` (privacy + ethics sections), `.gitignore` if any gap is found.

## Files That Must Not Be Modified

`contracts/` — frozen.

## Implementation Tasks

### Task 1 — Secret audit

Every row of `09` §Secrets. Scan the **entire git history**, not just the working tree:

```bash
git log -p | grep -iE "(sk-|gho_|0x[a-f0-9]{64}|SERPAPI_KEY=|IMGBB_KEY=|PRIVATE_KEY=)"
```

A key committed at M06 and deleted at M07 is still in history and still leaked.

### Task 2 — Untrusted input

Every row of `09` §Untrusted input. The size cap must be enforced **during** streaming, not after
— a cap checked after download does not protect against the attack it exists for.

SSRF: reject `file://`, `data:`, and internal/loopback addresses. Candidate URLs come from an
external provider; they are attacker-influenceable.

### Task 3 — Privacy

Confirm the bundle stores the embedding **digest**, never the embedding. Confirm `artifacts/` is
git-ignored except the one sample run, and that the sample run contains no identifiable private
individual. Confirm uploaded crops carry the one-day expiry.

Do not add persistence of face embeddings for convenience. No requirement needs it and it
enlarges the privacy surface for nothing.

### Task 4 — Ethics statements

The README carries all five statements from `09` §Ethical statements, in substance. Especially:

> The blockchain proves when a claim was recorded and that it has not changed since. It does not
> prove the claim is true. Anchoring a wrong match produces a permanent, tamper-evident record of
> a wrong match.

That distinction is the one most submissions get wrong, and stating it reads as sophistication
rather than hedging.

## Technical Constraints

Security controls are not performance knobs (`06` §Forbidden). Never relax a timeout or size cap
for throughput.

## Interfaces / Contracts

Unchanged.

## Error Handling

Security failures raise typed errors that describe the violation **without echoing the hostile
input** into logs.

## Performance Requirements

Streaming size checks add negligible overhead. Confirm rather than assume.

## Accuracy Requirements

None.

## Security Requirements

The milestone is the requirement. See `09` in full.

## Tests To Add

### Unit Tests
URL scheme rejection; internal-address rejection; content-type verified against bytes.

### Integration Tests
`test_no_secret_in_logs` captures all output across all commands and asserts no key material.
`test_download_caps` aborts an oversized response mid-stream.

### End-to-End Tests
None.

### Regression Tests
Full suite.

### Failure Tests
Oversized response; redirect loop; `file://` URL; loopback address; malformed content-type.

### Performance Tests
Streaming cap overhead measured.

### Accuracy Tests
None.

## Commands To Run

```bash
uv run pytest tests/test_security.py -v
git log -p | grep -iE "(sk-|gho_|0x[a-f0-9]{64}|_KEY=)" && echo "SECRET IN HISTORY" || echo "history clean"
git check-ignore -v .env
grep -rn "0x[a-fA-F0-9]\{64\}" src/ tests/ && echo "KEY LITERAL FOUND" || echo "no key literals"
uv run pytest -q
```

## Acceptance Criteria

| # | Criterion | Evidence |
|---|---|---|
| 1 | `.env` git-ignored | `git check-ignore` |
| 2 | No secret anywhere in git history | history scan |
| 3 | No secret in any log or error message | pytest |
| 4 | Size cap enforced during streaming | pytest |
| 5 | Timeouts on every outbound request | code review + pytest |
| 6 | SSRF protections active | pytest |
| 7 | Bundle stores embedding digest, not embedding | pytest |
| 8 | README carries all five ethics statements | README |

## Exit Gate

```text
MILESTONE STATUS: PASS | BLOCKED | FAILED
```

## Failure Conditions

Any secret in history or output. Size cap applied post-download. A missing timeout. Committed
biometric data of a private individual.

## Rollback Strategy

Security fixes are not rolled back. If a secret is found in history, rewriting history is
**required** before the repo goes public, and the key must be rotated regardless — assume it is
compromised.

## Documentation Updates

`SECURITY.md`; README privacy and ethics sections. `.agent-state`.

## Required Agent Report

Standard, plus the full control checklist with pass/fail per row.

## Questions That Require User Input

If a secret is found in history: confirm the rewrite and rotation plan before acting.

## Definition of Done

Eight criteria met. The secret checks are non-negotiable even if this milestone is compressed
for time (`10` §if-time).
