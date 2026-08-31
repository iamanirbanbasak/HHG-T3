# FINAL VALIDATION MATRIX

One executable checklist for every requirement. **No box is ticked without pasted output.**

For each row: Requirement / Evidence / Command / Expected / Actual / Status.

Run at M18, before submission. There are no resubmissions.

---

## R1 — Face identification

### [ ] R1.1 — A face is detected in the input image

```text
Requirement: FR-002, HC-01
Command:     uv run facechain scan --image <probe>.jpg
Expected:    bbox and det_score > 0.5 printed
Actual:      <paste>
Status:      PASS | FAIL
```

### [ ] R1.2 — A 512-d embedding is generated

```text
Requirement: FR-007, FR-008, HC-02
Command:     uv run pytest tests/test_embed.py -v
Expected:    shape (512,), float32, L2 norm == 1.0
Actual:      <paste>
Status:
```

### [ ] R1.3 — Zero faces raises rather than fabricating

```text
Requirement: FR-005
Command:     uv run facechain scan --image tests/fixtures/face_none.jpg; echo "exit=$?"
Expected:    NoFaceDetectedError, exit 2, no embedding produced
Actual:      <paste>
Status:
```

## R2 — Genuine search and face verification

### [ ] R2.1 — A genuine reverse image search executes

```text
Requirement: FR-012, HC-05
Command:     uv run pytest -m e2e tests/test_lens.py -v
Expected:    live provider call returns candidates
Actual:      <paste>
Status:
```

### [ ] R2.2 — The face crop is the query, not just the full photo

```text
Requirement: FR-012
Command:     uv run pytest tests/test_pipeline.py::test_crop_is_the_query -v
Expected:    pass; no 512-float payload sent to any provider
Actual:      <paste>
Status:
```

### [ ] R2.3 — A social candidate is discovered dynamically

```text
Requirement: FR-015, HC-04
Command:     uv run facechain search --image <probe>.jpg --show-candidates
Expected:    a real social post URL, not present anywhere in src/
Actual:      <paste>
Status:
```

### [ ] R2.4 — No hardcoded result is reachable

```text
Requirement: FR-055, HC-04
Command:     uv run pytest tests/test_no_hardcoding.py -v
             grep -rnE "(instagram|twitter|x|facebook)\.com" src/
Expected:    tests pass; grep returns nothing
Actual:      <paste>
Status:
```

### [ ] R2.5 — Candidates are independently face-verified

```text
Requirement: FR-018, HC-03, HC-06
Command:     uv run pytest tests/test_candidate_verification.py -v
Expected:    pass; and removing the candidate-embedding call makes a test FAIL
Actual:      <paste>
Status:
```

### [ ] R2.6 — Similarity is numeric and the threshold is applied

```text
Requirement: FR-019, FR-020, HC-07, HC-08
Command:     uv run facechain run --image <probe>.jpg --threshold 0.45 --network local
Expected:    a real cosine value shown alongside the threshold
Actual:      <paste>
Status:
```

### [ ] R2.7 — The highest scorer is selected

```text
Requirement: FR-021, HC-09
Command:     uv run pytest tests/test_candidate_verification.py::test_selects_highest -v
Expected:    pass
Actual:      <paste>
Status:
```

### [ ] R2.8 — Zero survivors is an honest negative, not a fabricated match

```text
Requirement: FR-022
Command:     uv run pytest tests/test_pipeline_no_match.py -v
Expected:    NoVerifiedMatchError; nothing anchored
Actual:      <paste>
Status:
```

## R3 — Blockchain anchoring and re-verification

### [ ] R3.1 — Evidence is canonicalised and hashed deterministically

```text
Requirement: FR-026, FR-027, HC-10, HC-11
Command:     uv run pytest tests/test_evidence.py -v
Expected:    golden hash matches; reordered keys produce identical bytes
Actual:      <paste>
Status:
```

### [ ] R3.2 — The hash is anchored on-chain

```text
Requirement: FR-031, HC-12
Command:     uv run facechain anchor --run-id <id> --network base-sepolia
Expected:    tx hash and record id; explorer link resolves
Actual:      <paste>
Status:
```

### [ ] R3.3 — The hash is read back FROM the chain

```text
Requirement: FR-038, HC-13
Command:     uv run pytest tests/test_verify.py::test_reads_from_chain -v
Expected:    pass; and stubbing the eth_call makes it FAIL
Actual:      <paste>
Status:
```

### [ ] R3.4 — Evidence is independently recomputed from local artifacts

```text
Requirement: FR-039, HC-14
Command:     uv run facechain verify --record-id <N> --network base-sepolia
Expected:    both hashes displayed, MATCH, block and network shown
Actual:      <paste>
Status:
```

### [ ] R3.5 — Verification works without the original hosted URLs

```text
Requirement: FR-040, HC-16, NFR-015
Command:     uv run pytest tests/test_verify.py::test_offline_verify -v
Expected:    pass with all outbound HTTP blocked except RPC
Actual:      <paste>
Status:
```

### [ ] R3.6 — Tampering with source evidence causes a mismatch

```text
Requirement: FR-045, FR-047, HC-15
Command:     uv run facechain verify --record-id <N> --tamper
Expected:    MISMATCH; mutation applied to post_text.txt, not to a digest field
Actual:      <paste>
Status:
```

### [ ] R3.7 — The original artifacts survive the tamper demo

```text
Requirement: FR-048
Command:     sha256sum artifacts/<run-id>/*   # before and after
Expected:    identical
Actual:      <paste>
Status:
```

## Constraints

### [ ] C1 — No web application

```text
Requirement: HC-18, NG-01
Command:     grep -rniE "fastapi|flask|django|uvicorn|express" pyproject.toml src/
Expected:    nothing
Actual:      <paste>
Status:
```

### [ ] C2 — README complete

```text
Requirement: FR-056
Check:       what it does / how to run / which blockchain / known limitations
Expected:    all four present, plus ethics and accuracy caveats
Actual:      <paste>
Status:
```

## Cross-cutting

### [ ] X1 — Provider errors distinguishable from empty results

```text
Requirement: FR-052, HC-17
Command:     uv run pytest tests/test_search_error.py -v
Expected:    500 raises SearchProviderError; empty 200 returns []
Actual:      <paste>
Status:
```

### [ ] X2 — Similarity never presented as a percentage

```text
Requirement: FR-051, HC-19
Command:     grep -rniE "[0-9]\s*%|percent|confidence" src/ README.md
Expected:    no hit adjacent to a similarity value
Actual:      <paste>
Status:
```

### [ ] X3 — Tests pass

```text
Requirement: NFR-017
Command:     uv run pytest -q --cov=src/facechain
Expected:    green; coverage >= 80% OR the actual number stated in the README
Actual:      <paste>
Status:
```

### [ ] X4 — Performance measured

```text
Requirement: NFR-001
Command:     cat bench/latest.json
Expected:    per-stage latencies recorded
Actual:      <paste>
Status:
```

### [ ] X5 — Accuracy: threshold status is stated honestly

```text
Requirement: NFR-004
Command:     cat eval/threshold_report.md   # or confirm README states it is uncalibrated
Expected:    distributions and separation, OR an explicit uncalibrated disclosure
Actual:      <paste>
Status:
```

### [ ] X6 — Security: no secrets anywhere

```text
Requirement: NFR-011
Command:     git log -p | grep -iE "(sk-|gho_|_KEY=|0x[a-f0-9]{64})"
             git check-ignore -v .env
Expected:    history clean; .env ignored
Actual:      <paste>
Status:
```

### [ ] X7 — Fresh clone reaches green from the README alone

```text
Requirement: NFR-016
Command:     cd /tmp && git clone <repo> fresh && cd fresh && uv sync && uv run pytest -q
Expected:    green
Actual:      <paste>
Status:
```

## Submission

### [ ] S1 — Screen recording

```text
Expected: full real path incl. tamper and negative path; link works logged-out
Actual:   <URL>
Status:
```

### [ ] S2 — Repository

```text
Expected: public, README complete, openable logged-out
Actual:   <URL>
Status:
```

### [ ] S3 — Adversarial audit

```text
Command:  execute 99-final-audit.md as a fresh agent
Expected: PASS or PASS WITH WARNINGS
Actual:   <verdict + findings>
Status:
```

---

## Sign-off

```text
Total rows:     28
Passed:
Failed:
Deferred (disclosed in README):

SUBMISSION READY: YES | NO
```

**Do not submit on NO.** There are no resubmissions.
