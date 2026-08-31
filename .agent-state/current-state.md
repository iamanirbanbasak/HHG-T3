# Project State

> Single source of truth for cross-agent handoff. **Never rely on conversational memory for
> project-critical state.** Another agent with no history must be able to resume from this file
> alone. Update it at the end of every milestone.

**Last updated:** 2026-09-01 (initial — no milestones executed yet)

---

## Current milestone

`M00 — Search Feasibility Spike` — **not started**

Blocked pending user answers to **AMB-05** (which public figure is the demo subject) and
**AMB-03** (does an imgbb API key exist). Both must be answered before M00 begins.

## Completed milestones

None.

## Current branch / state

`main`. Repository contains `docs/` and `agent-prompts/` only. No `src/`, no `pyproject.toml`.

## Implemented components

None. Target set is frozen in `02-architecture-execution.md` §1:

```text
face.detect  face.embed  face.similarity
search.uploader  search.lens  search.candidates
pipeline  evidence
chain.compile  chain.deploy  chain.registry
cli
config  errors
```

## Known failures

None — nothing built yet.

## Known risks

See `00-requirements-intelligence.md` §2.5 for all eleven. Live now:

- **RK-01** Lens may return no social URLs for a face crop — unresolved until M00
- **RK-02** imgbb hop unvalidated — unresolved until M00
- **RK-04** InsightFace/onnxruntime arm64 wheels unverified — unresolved until M00
- **RK-10** 19 milestones in 7 days — mitigated by the must-ship split in `10-deadline-plan.md`

## Assumptions

- The design spec `docs/superpowers/specs/2026-08-31-face-chain-design.md` is authoritative and
  approved.
- Python 3.11 on arm64 macOS; `uv` and `solc` present; Node not required.
- The demo subject is a public figure (primary) with the author's own face as the negative-path
  secondary run.

## Open decisions

| ID | Question | Blocks |
|---|---|---|
| AMB-01 | Source and consent basis of the threshold-calibration face set | M12 |
| AMB-02 | Base Sepolia wallet funding and key custody | M06 |
| AMB-03 | Does an imgbb account/API key exist | **M00** |
| AMB-04 | What the demo shows if the negative path produces a match | M17 |
| AMB-05 | Which public figure is the demo subject | **M00** |
| AMB-06 | How post text is obtained when Lens returns only a page URL | M08 |

## Test status

No test suite exists.

## Performance measurements

None.

## Accuracy measurements

None. `tau = 0.45` is the spec default and is **uncalibrated** until M12.

## Next milestone

`M00` — ask AMB-03 and AMB-05 together, then run the spike. Do not proceed to M01 on a `BLOCKED`
M00 gate without a user decision.
