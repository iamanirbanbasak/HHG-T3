# 10 — Deadline Plan

**Re-baselined 2026-09-01.** The spec's §12 table began Aug 31 and its Day-1 search spike did not
run. This plan supersedes it. Do not transcribe the spec's dates.

- **Today:** 2026-09-01
- **Deadline:** 2026-09-07, 23:59
- **Working days remaining:** 7 (Sep 1 through Sep 7)
- **No resubmissions.** A late discovery cannot be corrected after submission.

## Prioritisation rule

```text
highest uncertainty first
highest grading risk first
highest architectural dependency first
```

Everything except the search leg is deterministic local work that will certainly come together.
The search leg is the only part not under our control. **It goes first.**

Do not spend days polishing deterministic components before confirming that genuine Lens/social
search works for the intended subject (master §25).

## M00 is the gate

`M00-search-feasibility-spike.md` runs **before M01**. Its output is an answer, not code.

If M00 returns "Lens yields no social-media URLs for this subject", the project needs a decision
that day — a different subject, a second provider, or a documented deviation. Discovering that on
Sep 5 is unrecoverable; discovering it on Sep 1 costs an afternoon.

**M00 is blocked by AMB-03 (imgbb key) and AMB-05 (demo subject). Ask both before starting.**

## Schedule

| Day | Date | Milestones | Gate |
|---|---|---|---|
| 1 | Sep 1 | **M00**, M01 | Lens returns real social URLs for the subject; repo skeleton green |
| 2 | Sep 2 | M04, M05 | Golden hash + tamper tests exist and pass on `eth-tester` — written before the pipeline |
| 3 | Sep 3 | M02, M03, M07 | Probe embedding real; Lens integrated; dev stub deleted |
| 4 | Sep 4 | M08, M09, M10 | First genuine end-to-end run; verify + tamper pass |
| 5 | Sep 5 | M06, M11, M12 | Base Sepolia deploy; CLI demo-ready; `tau` measured |
| 6 | Sep 6 | M14, M15, M16 | Reliability, security, full regression at 80% |
| 7 | Sep 7 | M17, M18 | Record, audit, submit |

M13 (performance optimisation) is deliberately unscheduled. See below.

**Note the ordering inversion on Day 2:** evidence and chain (M04, M05) come before face
detection (M02, M03). This is intentional. The golden-hash and tamper tests are the two that
protect the actual claim being made to judges, they have zero external dependencies, and writing
them first means the pipeline is built against a fixed contract rather than the reverse.

## Must-ship vs if-time

**Must ship** — the project fails grading without these:

```text
M00  search feasibility          (gates everything)
M01  repository foundation
M02  face detection              HC-01
M03  embedding & similarity      HC-02
M04  evidence & hashing          HC-10, HC-11
M05  contract & local chain      HC-12
M07  upload + Lens               HC-05
M08  candidate filtering         HC-06
M09  candidate face verification HC-03, HC-06, HC-07, HC-08, HC-09
M10  end-to-end + verify/tamper  HC-13, HC-14, HC-15, HC-16
M11  CLI & demo                  the recording is the deliverable
M17  demo readiness              submission artifact S1
M18  final submission validation HC-04, C2
```

**If time** — valuable, degradable:

| Milestone | If dropped | Degraded form |
|---|---|---|
| M06 public testnet deploy | record against `local` eth-tester; the task explicitly permits a simulated chain (RK-05) | keep `local` path green |
| M12 accuracy calibration | `tau` stays the documented default | **still record that it is uncalibrated in the README** — do not imply it was measured |
| M13 performance optimisation | **first to drop** (RK-10) | measure and record; defer optimisation |
| M14 reliability | reduce to the highest-value rows: 7, 8, 9, 12, 13 | the rest documented as untested |
| M15 security | secrets and download caps are non-negotiable; the rest degradable | never drop the secret checks |
| M16 full regression | reduce coverage target below 80% | **state the actual number**, do not claim 80% |

Honesty rule: a dropped milestone is disclosed in the README's limitations. Claiming coverage or
calibration that was not achieved is worse than the gap itself — a reviewer who finds one
overstated claim discounts everything else.

## Daily checkpoint

End of each day, update `.agent-state/current-state.md` with:

```text
milestones completed today
milestones slipped
new blockers
whether the must-ship list is still reachable
```

If the must-ship list stops being reachable, say so that day. The correct response is to drop
if-time work, not to compress testing on must-ship milestones.

## Buffer

Day 7 holds both the recording and submission. That is thin. If Day 6 finishes early, record a
rehearsal take on Day 6 — a rehearsal surfaces missing model caches, expired uploads, and empty
faucet wallets while there is still a day to fix them (RK-09, RK-05).
