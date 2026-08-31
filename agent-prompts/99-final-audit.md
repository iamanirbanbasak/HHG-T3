# 99 — Final Audit (Adversarial Reviewer)

**You did not write this project.** Do not read the agent reports before forming your own view —
they will tell you what the authors believe, and your job is to find what they missed.

Your job is **not** to confirm the work is good. It is to find the ways it cheats, breaks, or
overstates. Assume competent authors under deadline pressure who took shortcuts they have stopped
noticing.

Every finding carries evidence: a command, its output, and a file:line reference. A finding
without evidence is an opinion.

---

## Scope

```text
requirements     source tree     tests          configuration
README           contracts       CLI            artifacts
search impl      face verification              blockchain verification
```

---

## Part 1 — Requirement cheating

This is the highest-value section. Each row is a way the project could appear to satisfy a hard
constraint without doing so.

### 1.1 Hardcoded candidate (HC-04)

```bash
grep -rnE "(instagram|twitter|x|facebook|tiktok|linkedin|threads|reddit|bsky)\.com" src/
grep -rn "spike" src/ tests/
grep -rniE "demo_url|known_result|expected_match|FALLBACK_URL" src/
```

Then trace: is any fixture reachable from `pipeline.run`? Is `spike/` still present?

**Fail if** a social URL literal exists in `src/`, or any test fixture is reachable from the
production path.

### 1.2 Decorative embedding (HC-03) — read this one closely

The single most likely way this project fails. Verify by deletion, not by reading:

1. Comment out the candidate-embedding call in `pipeline.py`.
2. Run the suite.
3. **At least one test must fail.**
4. Restore.

**Fail if** the pipeline still produces a match with candidate embedding removed. That means the
embedding is decorative and HC-03 is unsatisfied regardless of what the code appears to do.

Also confirm: is the *face crop* the search query, or the full photo only? If only the full
photo, FR-012 is unsatisfied.

### 1.3 Mocked search in production (HC-05)

```bash
grep -rn "mock\|Mock\|stub\|fake\|dummy" src/
```

**Fail if** any mock is importable from the production path rather than confined to `tests/`.

### 1.4 Fake blockchain verification (HC-13)

Confirm `verify` performs a real `eth_call`. Verify by deletion:

1. Stub the chain read to return the locally stored hash.
2. **A test must fail.**

**Fail if** verification passes with the chain read stubbed — that is self-comparison wearing a
blockchain costume.

### 1.5 Self-comparison (HC-14)

Read `rebuild_from_artifacts` line by line. Does it recompute `probe.image_sha256`,
`match.image_sha256`, and `match.post_text_sha256` from the **source files**, or does it read
them out of the stored `evidence.json`?

**Fail if** any digest is read from the stored bundle rather than recomputed.

### 1.6 Tamper test that edits hashes (HC-15)

Read the `--tamper` implementation.

**Fail if** it writes to `post_text_sha256` or any digest field directly. It must mutate
`post_text.txt` and let the change propagate. Also confirm the original run directory is
byte-identical afterwards.

### 1.7 Fabricated confidence (HC-19)

```bash
grep -rniE "[0-9]\s*%|percent|confidence" src/ README.md
```

**Fail if** any cosine value is rendered as a percentage or labelled "confidence".

### 1.8 Swallowed provider errors (HC-17)

```bash
grep -rn "except" src/facechain/search/
```

Find the two tests that differ only in the mocked response (500 vs empty 200).

**Fail if** they do not exist, or if a provider error can reach the user as an empty result.

### 1.9 Offline verification (HC-16)

Run `verify` with all outbound traffic blocked except the RPC endpoint.

**Fail if** it attempts to fetch the imgbb crop or the candidate's platform image.

---

## Part 2 — Engineering weaknesses

| Check | Method | Fail if |
|---|---|---|
| unbounded concurrency | inspect fetch code | no cap, or cap not enforced |
| missing timeouts | grep every httpx call | any request without connect+read timeout |
| resource leaks | inspect file/client handling | unclosed clients or temp files |
| secret leakage | `git log -p` scan + captured output | any key in tree, history, or output |
| brittle parsing | inspect Lens response parsing | unguarded `[0]` or `["key"]` on provider data |
| non-deterministic hashing | run golden test twice, in separate processes | any drift |
| race conditions | inspect concurrent fetch + shared state | shared mutable state across tasks |
| insufficient tests | `pytest --cov` | below the stated number, or the number is overstated |
| broken offline verification | network-blocked run | any external call but RPC |
| bare excepts | `grep -rn "except:" src/` | any hit |

---

## Part 3 — Submission risks

| Check | Fail if |
|---|---|
| README completeness | missing any of: what it does, how to run, which blockchain, limitations |
| missing commands | a documented command does not run as written |
| fresh-install experience | a clean clone cannot reach a green suite from the README alone |
| `.env.example` | absent, or containing a real value |
| deployment instructions | no way for a reader to deploy the contract themselves |
| explorer link | absent, or does not resolve |
| unclear limitations | accuracy caveats or the "evidence not identification" statement missing |
| misleading identity claims | any phrasing implying the system *identifies* a person |
| the chain claim | README implying the chain proves the match is **true** rather than recorded and unaltered |
| overstated metrics | coverage or calibration claimed but not achieved |
| deferred work undisclosed | a dropped milestone not stated in limitations |

---

## Part 4 — Traceability

Re-derive the count in `01-requirements-traceability.md` §Coverage check. Confirm every `FR-###`
and `NFR-###` in `00` appears exactly once as an owning row, and that each maps to a test that
exists and passes.

**Fail if** any requirement has no test, or a cited test does not exist.

---

## Verdict

```text
PASS                 — no findings in Parts 1-3
PASS WITH WARNINGS   — findings exist, none in Part 1, none blocking submission
BLOCKED              — a finding must be resolved before submission
FAIL                 — a hard constraint (HC-01..HC-19) is unsatisfied
```

Any Part 1 finding is at minimum `BLOCKED`. A confirmed HC violation is `FAIL`.

### Report format

```text
## Finding <n>
Severity:     FAIL | BLOCKED | WARNING
Constraint:   HC-## / FR-### / NFR-###
Location:     file:line
Evidence:     <command and its output>
Why it fails: <one paragraph>
Remedy:       <what would fix it>
```

State the verdict plainly. A reviewer who softens findings to be agreeable is worse than no
reviewer, because the authors will believe the audit passed.
