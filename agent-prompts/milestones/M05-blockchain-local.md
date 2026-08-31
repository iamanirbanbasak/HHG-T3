# Milestone M05 — Blockchain Contract & Local Chain

## Objective

Write `FaceMatchRegistry.sol`, compile it with `py-solc-x`, and deploy/anchor/read it against
`eth-tester` in-process.

## Why This Milestone Exists

HC-12. Doing this on a local in-process chain first means the entire chain layer is proven before
any testnet, faucet, or RPC dependency enters the picture (RK-05).

## Requirements Covered

Owns: FR-029, FR-030, FR-031, FR-032, FR-033, FR-034, FR-035, FR-037, NFR-010.

## Preconditions

M01 `PASS`. `solc` available or installable via `py-solc-x`.

## Inputs

Spec §6 (full contract source). `02` §3.9, §10.

## Expected Repository State Before Starting

`config.py`, `errors.py`, `evidence.py` exist; suite green.

## Files To Create

```text
contracts/FaceMatchRegistry.sol
src/facechain/chain/compile.py
src/facechain/chain/deploy.py
src/facechain/chain/registry.py
tests/test_registry.py
```

## Files To Modify

`src/facechain/chain/__init__.py`, `pyproject.toml` if solc pinning needs it.

## Files That Must Not Be Modified

`evidence.py`, `face/`, `config.py`.

## Implementation Tasks

### Task 1 — Contract

Spec §6 verbatim: `Record` struct, append-only `_records`, `MatchAnchored` event, `anchor`,
`get`, `verify`, `count`. `require` guards on empty hash and empty URL. Solidity 0.8.24.

**No update path, no delete path, no owner, no upgradeability** (FR-037). Mutability defeats the
entire purpose of the project.

`postUrl` is stored in cleartext, deliberately — a reviewer must be able to open the transaction
on a block explorer and read the matched post (spec §6).

### Task 2 — Compilation

`py-solc-x` with solc **pinned to 0.8.24**. No Foundry, no Hardhat, no Node toolchain (spec §8
rejected alternatives). Installing a Node-based toolchain here is a material deviation — ask.

### Task 3 — `Registry` wrapper

Provider-agnostic per `02` §3.9. It receives a `Web3` instance; it never constructs one and never
reads the network from config. The same object must work unchanged against `eth-tester` and Base
Sepolia — M06 depends on that being literally true.

### Task 4 — eth-tester harness

A pytest fixture giving a funded in-process chain. No RPC URL, no network, no external binary
(NFR-010).

## Technical Constraints

`web3[tester]` only. Chain tests must run offline.

## Interfaces / Contracts

`02` §3.9, exactly.

## Error Handling

RPC failure, revert, and receipt failure all raise `ChainError` carrying the revert reason where
available. Never swallow a failed receipt — a silently failed anchor produces a receipt file
pointing at a transaction that did nothing.

## Performance Requirements

Local anchor under 1s. Record it as the M13 baseline for the chain stage.

## Accuracy Requirements

None.

## Security Requirements

Private keys never logged, never in exception messages (NFR-011). The eth-tester fixture uses
throwaway keys that never touch `.env`.

## Tests To Add

### Unit Tests
`similarity_bps` boundary values are accepted as `uint16` without overflow.

### Integration Tests
Compile → deploy → anchor → `get` → `count` → on-chain `verify`, all on `eth-tester`. Round-trip
every `Record` field. `count()` increments per anchor. ABI exposes no mutation path.

### End-to-End Tests
None here — M06 owns the public testnet.

### Regression Tests
Full suite.

### Failure Tests
Empty hash reverts; empty URL reverts; a revert surfaces as `ChainError` with the reason.

### Performance Tests
Local anchor latency recorded.

### Accuracy Tests
None.

## Commands To Run

```bash
uv run pytest tests/test_registry.py -v
uv run python -c "from facechain.chain.compile import compile_registry; a,b = compile_registry(); print(len(a), len(b))"
uv run pytest -q
```

## Acceptance Criteria

| # | Criterion | Evidence |
|---|---|---|
| 1 | Contract compiles with solc 0.8.24 | pytest |
| 2 | Deploys on eth-tester | pytest |
| 3 | Anchor emits `MatchAnchored`, returns id | pytest |
| 4 | `get` round-trips all fields | pytest |
| 5 | `count` increments | pytest |
| 6 | Empty hash and empty URL revert | pytest |
| 7 | No mutation path in the ABI | pytest |
| 8 | No network access required | offline test run |

## Exit Gate

```text
MILESTONE STATUS: PASS | BLOCKED | FAILED
```

## Failure Conditions

Any setter or delete in the ABI. Chain tests requiring a live RPC. A swallowed failed receipt.

## Rollback Strategy

Revert `chain/` and `contracts/`. Nothing depends on it yet.

## Documentation Updates

README: which blockchain, why, and how to run against `local`. `.agent-state`.

## Required Agent Report

Standard, plus contract bytecode size and local anchor latency.

## Questions That Require User Input

None here. **AMB-02** (wallet funding, key custody) becomes blocking at M06 — raise it now so it
is resolved before that milestone starts.

## Definition of Done

Eight criteria met; entire chain layer proven offline.
