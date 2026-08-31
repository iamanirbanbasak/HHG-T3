# Milestone M10 — End-to-End Pipeline, Re-verification & Tamper

## Objective

Complete `pipeline.run`, persist artifacts, anchor on-chain, and implement `verify` and
`verify --tamper`.

## Why This Milestone Exists

This milestone closes HC-13, HC-14, HC-15, and HC-16 — the entire re-verification half of the
project's claim. It is the milestone an adversarial reviewer scrutinises hardest, because it is
where a project can most easily *appear* to verify something while actually comparing a file to
itself.

## Requirements Covered

Owns: FR-038 through FR-048, NFR-015.

## Preconditions

M04, M05, M09 all `PASS`.

## Inputs

`02` §3.7, §3.8, §9, §10. Spec §7.

## Expected Repository State Before Starting

Evidence, chain, and candidate verification each green in isolation.

## Files To Create

```text
tests/test_verify.py
tests/test_verify_tamper.py
```

## Files To Modify

```text
src/facechain/pipeline.py      # complete run()
src/facechain/evidence.py      # persist artifacts per 02 §9
src/facechain/cli.py           # verify, anchor
```

## Files That Must Not Be Modified

`contracts/FaceMatchRegistry.sol` — frozen at M05.

## Implementation Tasks

### Task 1 — Persist artifacts

Write `artifacts/<run-id>/` exactly per `02` §9: `probe.jpg`, `probe_aligned.png`,
`candidate.jpg`, `post_text.txt`, `evidence.json`, `receipt.json`.

These files are the **source evidence**. Verification recomputes from them; the tamper demo
mutates one of them. Their fidelity is the whole point.

### Task 2 — Anchor

Build the bundle, canonicalise, keccak256, `Registry.anchor(hash, post_url, sim_bps)`. Write
`receipt.json` with record id, tx hash, network, block, contract address.

### Task 3 — `verify`, the careful part

```text
1. Fetch Record.evidenceHash from the chain via eth_call      ← a REAL network read
2. Rebuild the bundle from artifacts/<run-id>/ on disk
   recomputing probe.image_sha256, match.image_sha256, match.post_text_sha256
   from the stored SOURCE FILES
3. Canonicalise, keccak256
4. Print both hashes side by side, with block number and network
5. MATCH → exit 0.  MISMATCH → EvidenceIntegrityError, exit 1
```

**The failure mode to design against:** a verifier that loads the stored evidence hash for *both*
sides and compares it to itself. That proves nothing and is an easy accident. The on-chain read
and the local recompute are separate code paths that meet only at the comparison.

**Recomputation reads local disk only** (FR-040, HC-16). Never re-fetch the imgbb crop (expired
after a day) or the candidate's platform image (may 403 or be deleted). Verification must keep
working indefinitely after recording, on a laptop reaching nothing but the RPC endpoint.

### Task 4 — `verify --tamper`

```text
1. Copy artifacts/<run-id>/ to a scratch directory
2. Mutate ONE BYTE of post_text.txt IN THE COPY
3. Rebuild the bundle normally from the copy
4. The changed text yields a different post_text_sha256
   → a different bundle → a different hash
5. Compare against the unchanged on-chain hash → MISMATCH
6. The original run directory is byte-identical afterwards
```

**Mutate the source evidence, never a digest field.** Editing `post_text_sha256` inside the
bundle directly would be a self-referential trick that a reviewer reading the code would rightly
discount. Only source-level mutation demonstrates the chain catching a real alteration
(FR-045, HC-15).

### Task 5 — Anti-cheat tests

- `test_reads_from_chain` — **fails if the `eth_call` is stubbed out**
- `test_mutates_source_not_digest` — asserts the bundle's digest field is never written directly
- `test_originals_intact` — pre/post digests of the run directory are identical
- `test_offline_verify` — passes with all outbound HTTP blocked **except** RPC

Demonstrate each red before reverting (`05` §Anti-cheat tests).

## Technical Constraints

`verify` makes exactly **one** external call: the `eth_call`. Any other outbound request is a
failure of FR-040.

## Interfaces / Contracts

`02` §3.7, §3.8, §3.9, §9.

## Error Handling

Per `02` §7. Note the asymmetry: `EvidenceIntegrityError` is the **success** condition of
`--tamper` (exit 0) and the **failure** condition of plain `verify` (exit 1). The CLI must
distinguish them (FR-043, FR-047).

Missing artifact → typed error naming the file. Missing record id → `ChainError`.

## Performance Requirements

Verification under 3s including the RPC round-trip. It contains no model inference — if it is
slow, something is being re-downloaded, which is itself an FR-040 violation.

## Accuracy Requirements

None. Verification is exact-match on bytes, never approximate.

## Security Requirements

`--tamper` operates on a scratch copy under `tempfile`, cleaned up afterwards (`09`). It must be
impossible for `--tamper` to corrupt real evidence — assert the originals afterwards.

## Tests To Add

### Unit Tests
Exit-code mapping for each error type.

### Integration Tests
Full anchor → verify round-trip on `eth-tester`, MATCH. `test_reads_from_chain`.
`test_rebuild_from_disk` — digests recomputed from source, not read from the bundle.

### End-to-End Tests
Marked `e2e`: full run against real services and testnet, then verify.

### Regression Tests
Full suite.

### Failure Tests
Corrupted artifact → MISMATCH. Missing artifact → typed error. Tampered artifact → MISMATCH.
`test_offline_verify` with HTTP blocked except RPC.

### Performance Tests
Verification latency recorded.

### Accuracy Tests
None.

## Commands To Run

```bash
uv run pytest tests/test_verify.py tests/test_verify_tamper.py -v
uv run pytest -q
uv run facechain run --image <probe>.jpg --network local
uv run facechain verify --record-id 0 --network local
uv run facechain verify --record-id 0 --network local --tamper
sha256sum artifacts/<run-id>/*        # before and after --tamper, must be identical
```

## Acceptance Criteria

| # | Criterion | Evidence |
|---|---|---|
| 1 | Hash read from chain via `eth_call` | pytest; stubbing it fails a test |
| 2 | Bundle rebuilt from local source files | pytest |
| 3 | Verify passes offline except RPC | pytest with HTTP blocked |
| 4 | Both hashes displayed with block and network | captured stdout |
| 5 | MATCH exit 0, MISMATCH exit 1 | exit codes |
| 6 | `--tamper` mutates source, not a digest | pytest |
| 7 | `--tamper` produces MISMATCH | captured stdout |
| 8 | Originals byte-identical after `--tamper` | sha256sum before/after |
| 9 | All four anti-cheat tests demonstrated red | agent report |

## Exit Gate

```text
MILESTONE STATUS: PASS | BLOCKED | FAILED
```

## Failure Conditions

Each of these is `FAILED`:

- verify comparing the stored hash against itself
- verify re-fetching any hosted URL
- `--tamper` editing a digest field instead of source evidence
- `--tamper` mutating the real run directory

## Rollback Strategy

Revert `cli.py` verify commands and the `pipeline.run` completion. M09 and M05 remain green.

## Documentation Updates

README: the full verify flow, the tamper demo, and — importantly — the statement that the chain
proves *when a claim was recorded*, never that the claim is true. `.agent-state`.

## Required Agent Report

Standard, plus both hash values, the tamper output, and evidence that all four anti-cheat tests
were demonstrated failing before revert.

## Questions That Require User Input

None expected.

## Definition of Done

Nine criteria met. This is the milestone whose failure would make the whole submission hollow —
do not mark it `PASS` on partial evidence.
