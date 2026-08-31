# Project State

**Last updated:** 2026-09-01

---

## Current milestone

M07 (search integration) — **BLOCKED on a valid SerpAPI key.**

## Completed milestones

| Milestone | Status | Evidence |
|---|---|---|
| M00 environment + upload gate | PARTIAL PASS | InsightFace runs on arm64 (RK-04 closed); imgbb upload verified live (RK-02 closed). **Lens half not run** — key rejected. |
| M01 repository foundation | PASS | config, errors, scaffold; 15 tests |
| M02 face detection | PASS | real SCRFD; 6 faces on fixture, det_score 0.92 |
| M03 embedding + similarity | PASS | 512-d L2-normalised; same-face 1.0000, different-face 0.0645 |
| M04 evidence + hashing | PASS | canonical JSON, golden hash, 25 tests |
| M05 contract + local chain | PASS | solc 0.8.24, eth-tester, 12 tests |
| M08 candidate filtering | PASS | allowlist, dedupe, SSRF, size caps |
| M09 candidate verification | PASS | independent re-embedding; anti-cheat test in place |
| M10 end-to-end + verify/tamper | PASS | full run anchored + verified + tampered on local chain |
| M11 CLI | PASS | six commands, exit codes, output discipline |
| M16 regression + import graph | PASS | 184 tests, 80% coverage, offline |

## Not started

M06 (public testnet — needs funded wallet, AMB-02), M12 (calibration — needs AMB-01),
M13 (performance), M14 (full reliability matrix), M15 (security milestone),
M17 (recording), M18 (submission).

## Test status

```
184 passed, 80% coverage, fully offline
```

## Known failures

None in the suite.

## Known risks

- **RK-01 UNRESOLVED — the highest-uncertainty item in the project.** Whether Google Lens returns
  social-media URLs for a bare face crop has never been tested, because no valid SerpAPI key is
  available. Everything downstream is built and tested against injected fakes.
- RK-05 public testnet unexercised; `local` path green as fallback.
- RK-09 model pack is now cached locally (~281MB), so demo cold-start is mitigated.

## Assumptions

- Provider injection replaces the spec's dev-stub approach, so no stub exists in `src/` to delete
  (RK-06 dissolved rather than managed).
- `w600k_r50` recorded as the embedder, not the spec's `arcface_r100_glint360k`: buffalo_l ships
  r50 and the bundle must name the model that actually ran.

## Open decisions

| ID | Question | Blocks |
|---|---|---|
| **NEW** | A valid SerpAPI key, or a decision to use a different provider | **M07, and RK-01** |
| AMB-01 | Consent basis for the calibration face set | M12 |
| AMB-02 | Base Sepolia wallet funding and key custody | M06 |
| AMB-04 | What the demo shows if the negative path produces a match | M17 |
| AMB-05 | Which public figure is the demo subject | M17 |
| AMB-06 | RESOLVED — post_text records provider-returned title/source, labelled as such | — |

## Accuracy measurements

`tau = 0.45` **uncalibrated**. Smoke check only: same-face cosine 1.0000, different-face 0.0645.

## Next milestone

M07 once a working search key exists. Until then the search leg cannot be exercised live and
RK-01 stays open.
