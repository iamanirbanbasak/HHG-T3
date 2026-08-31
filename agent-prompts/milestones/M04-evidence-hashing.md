# Milestone M04 — Evidence & Deterministic Hashing

## Objective

Implement `evidence`: artifact digests, bundle assembly, canonical serialisation, keccak256
hashing, and `similarity_bps`. Establish the golden-file tests.

## Why This Milestone Exists

HC-10 and HC-11. This milestone and M05 are scheduled **before** the face pipeline (see `10`)
because the golden-hash and tamper tests protect the actual claim made to judges, they have zero
external dependencies, and writing them first fixes the contract the pipeline is built against.

Canonical JSON is the single highest-leverage correctness detail in the project. Without stable
key ordering and separators, verification fails on serialisation noise rather than on tampering —
and the failure looks exactly like a real tamper detection, which is worse than no test at all.

## Requirements Covered

Owns: FR-023, FR-024, FR-025, FR-026, FR-027, FR-028, NFR-007, NFR-008.

## Preconditions

M01 `PASS`. M02/M03 are **not** required — this milestone consumes plain data.

## Inputs

Spec §5.1 (bundle schema), §5.2 (hashing), §5.3 (bps encoding). `02` §3.8, §9.

## Expected Repository State Before Starting

`config.py`, `errors.py` exist; suite green.

## Files To Create

```text
src/facechain/evidence.py
tests/test_evidence.py
tests/fixtures/golden_bundle.json
tests/fixtures/golden_hash.txt
```

## Files To Modify

None.

## Files That Must Not Be Modified

`face/`, `config.py`, `errors.py`.

## Implementation Tasks

### Task 1 — Canonical serialisation

Exactly:

```python
json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
```

No variations. No pretty-printing anywhere on this path.

### Task 2 — Two hash algorithms, kept separate

- artifact digests → **SHA-256**, lowercase hex, no prefix
- canonical bundle → **keccak256**, 32 bytes, Solidity-native

They are used in exactly one place each. Do not merge them or "simplify" to one algorithm
(master §14).

### Task 3 — Bundle assembly and rebuild

`build_bundle(...)` produces the `hhg-t3/evidence/v1` schema from spec §5.1 exactly.

`rebuild_from_artifacts(run_dir)` reconstructs the bundle by **recomputing every digest from the
stored source files** — `probe.jpg`, `candidate.jpg`, `post_text.txt`. It must never read a
digest out of a stored bundle and reuse it (FR-039, HC-14). This is the function M10's verify
depends on, and the one an adversarial reviewer will read first.

### Task 4 — `similarity_bps`

`max(0, min(10000, round(cosine * 10000)))`. Cosine can be negative; clamping keeps the on-chain
type unsigned. Document in the docstring that this is a **raw cosine encoding, not a
percentage** (FR-051).

### Task 5 — Golden files

Commit a fixed bundle and its expected keccak256. If this hash ever changes, the change must be
explained. Never regenerate the golden file to turn a red test green (`05` §Golden files).

## Technical Constraints

`evidence.py` imports stdlib plus `eth_utils.keccak` only. It never imports `face.*`, `search.*`,
or `chain.*` — it receives plain data (`02` §2).

## Interfaces / Contracts

`02` §3.8, exactly. Artifact layout per `02` §9.

## Error Handling

Missing artifact file → typed error naming the file, never a bare `KeyError` or `FileNotFoundError`
escaping to the CLI. Schema violation → `FaceChainError` naming the offending key.

## Performance Requirements

Hashing is negligible. Avoid re-serialising the same bundle repeatedly within one run.

## Accuracy Requirements

None directly, but `similarity_bps` must round-trip: `bps/10000` recovers cosine to 4 decimals.

## Security Requirements

The bundle stores the **digest** of the embedding, never the embedding itself (`09` §Privacy).
No secret ever enters the bundle.

## Tests To Add

### Unit Tests
Canonical bytes identical for reordered-key inputs; golden hash matches the committed value;
SHA-256 digests match a `hashlib` reference; bundle schema has all spec §5.1 keys and no extras;
`similarity_bps` clamps `-0.3 → 0` and `1.0 → 10000`; rounding correct at boundaries.

### Integration Tests
`rebuild_from_artifacts` on a synthetic run directory reproduces the original hash. Then mutate
`post_text.txt` by one byte and confirm the hash **changes** — this is the M10 tamper mechanism
proven at the unit level, before the CLI exists.

### End-to-End Tests
None.

### Regression Tests
Full suite.

### Failure Tests
Missing artifact; unreadable artifact; bundle with an unexpected key.

### Performance Tests
None required.

### Accuracy Tests
`similarity_bps` round-trip.

## Commands To Run

```bash
uv run pytest tests/test_evidence.py -v
uv run python -c "from facechain.evidence import canonicalise; print(canonicalise({'b':1,'a':2}))"
uv run pytest -q
```

## Acceptance Criteria

| # | Criterion | Evidence |
|---|---|---|
| 1 | Canonical bytes stable across key ordering | pytest |
| 2 | Golden hash matches | pytest |
| 3 | SHA-256 and keccak256 both present, not merged | code review + pytest |
| 4 | `rebuild_from_artifacts` recomputes from source files | pytest |
| 5 | One-byte mutation changes the hash | pytest |
| 6 | `similarity_bps` clamps and rounds correctly | pytest |
| 7 | Hash stable across a fresh interpreter | subprocess test |

## Exit Gate

```text
MILESTONE STATUS: PASS | BLOCKED | FAILED
```

## Failure Conditions

Any non-determinism in serialisation. `rebuild_from_artifacts` reading a stored digest instead of
recomputing — this hollows out HC-14 and is a `FAILED`, not a warning.

## Rollback Strategy

Revert `evidence.py` and its fixtures. Nothing depends on it yet.

## Documentation Updates

README: evidence bundle schema and the two-algorithm rationale. `.agent-state`.

## Required Agent Report

Standard, plus the golden hash value.

## Questions That Require User Input

**AMB-06** — how is `post_text` obtained when Lens returns only a page URL and a thumbnail? The
bundle hashes `post_text_sha256` and the M10 tamper demo mutates that file, so it must exist. If
post text cannot be retrieved, the tamper target must change and this schema changes with it.
Raise it now; M08 is where it becomes blocking.

## Definition of Done

Seven criteria met; golden files committed; AMB-06 raised.
