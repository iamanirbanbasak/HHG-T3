# Milestone M06 — Blockchain Deployment & Registry (Public Testnet)

## Objective

Deploy `FaceMatchRegistry` to Base Sepolia and prove the same `Registry` code path works against
a public network with no changes.

## Why This Milestone Exists

A live block-explorer link is the single most legible piece of evidence a judge can check in ten
seconds. It is also the milestone most exposed to external failure (RK-05), which is why the
`local` path from M05 stays green throughout as the fallback.

## Requirements Covered

Owns: FR-036.
Exercises on a public network: FR-030, FR-031, FR-032.

## Preconditions

M05 `PASS`. **AMB-02 answered**: the wallet exists, holds Base Sepolia faucet ETH, and key
custody is agreed.

## Inputs

`RPC_URL`, `PRIVATE_KEY` from `.env`. Spec §6 §Networks.

## Expected Repository State Before Starting

Chain layer green on `eth-tester`.

## Files To Create

```text
tests/test_deploy_network.py       # marked e2e
```

## Files To Modify

```text
src/facechain/config.py            # network selection at the config boundary
src/facechain/chain/deploy.py      # network-aware provider construction
README.md
.env.example
```

## Files That Must Not Be Modified

`contracts/FaceMatchRegistry.sol` — the contract is frozen at M05. Redeploying a changed contract
invalidates M05's test evidence.
`chain/registry.py` — if it needs changing to work on a public network, M05's provider-agnostic
claim was false. Fix the provider construction instead.

## Implementation Tasks

### Task 1 — Network selection at the configuration boundary

`Config.network` selects `local` or `base-sepolia`. Provider construction happens once, in
`deploy.py`/`cli.py`, driven by config. **No business-logic module learns which network it is
on** (FR-036).

### Task 2 — Deploy

Deploy to Base Sepolia. Record address, tx hash, and block. Write the address to `.env` and
document it in the README with a Basescan link.

### Task 3 — Marked e2e test

`@pytest.mark.e2e`, skipped by default, that anchors and reads back on the live testnet. It must
never run in the ordinary suite (NFR-009).

### Task 4 — Fallback rehearsal

Confirm `--network local` still works end to end. If Base Sepolia is unavailable on recording
day, this is the recording (RK-05).

## Technical Constraints

Base Sepolia by default. Switching to Ethereum Sepolia or Polygon Amoy is a one-line `Config`
change and is **not** a deviation — nothing in the code is Base-specific.

## Interfaces / Contracts

`02` §3.9 unchanged. Only provider construction differs.

## Error Handling

RPC unreachable, insufficient funds, nonce collision, and timeout all raise `ChainError` with an
actionable message. "Insufficient funds" must say so plainly — it is the single most likely live
failure and a cryptic message costs demo time.

## Performance Requirements

Record anchor latency on Base Sepolia (~2s expected). Compare with the local baseline from M05.

## Accuracy Requirements

None.

## Security Requirements

`PRIVATE_KEY` from `.env` only, never a literal, never logged, never in an error message
(NFR-011). Use a **throwaway wallet holding only faucet ETH** — never a wallet with mainnet value.
The repo is destined to be public.

## Tests To Add

### Unit Tests
Config network selection resolves the right provider without constructing one.

### Integration Tests
`local` path still green — full M05 suite unchanged.

### End-to-End Tests
Marked `e2e`: deploy or reuse address, anchor, read back, verify the explorer URL resolves.

### Regression Tests
Full offline suite still passes with no `RPC_URL` set.

### Failure Tests
Missing `RPC_URL`; missing `PRIVATE_KEY`; unfunded wallet — each a clear `ChainError`.

### Performance Tests
Testnet anchor latency recorded.

### Accuracy Tests
None.

## Commands To Run

```bash
uv run facechain deploy --network base-sepolia
uv run pytest -m e2e tests/test_deploy_network.py -v
uv run pytest -q                      # offline suite must still pass
uv run facechain deploy --network local
```

## Acceptance Criteria

| # | Criterion | Evidence |
|---|---|---|
| 1 | Contract live on Base Sepolia | Basescan URL |
| 2 | Anchor + readback on testnet | e2e test output |
| 3 | `registry.py` unchanged from M05 | `git diff` empty for that file |
| 4 | Offline suite green without RPC | pytest output |
| 5 | `local` fallback still works | command output |
| 6 | No secret in any log | grep of captured output |

## Exit Gate

```text
MILESTONE STATUS: PASS | BLOCKED | FAILED
```

`BLOCKED` on unfunded wallet is acceptable — proceed with `local` and revisit. This milestone is
**if-time** per `10`; do not let it block M07.

## Failure Conditions

`registry.py` needing changes to work on a public network. A key appearing in any output.

## Rollback Strategy

Set `network = local` in config. Everything else continues working. This is the RK-05 fallback,
tested rather than hoped for.

## Documentation Updates

README: which blockchain, contract address, Basescan link, faucet instructions. `.agent-state`.

## Required Agent Report

Standard, plus contract address, tx hash, explorer URL, and both anchor latencies.

## Questions That Require User Input

**AMB-02** if unresolved — blocks this milestone only, not the project.

## Definition of Done

Six criteria met, or a documented `BLOCKED` with the `local` path proven as fallback.
