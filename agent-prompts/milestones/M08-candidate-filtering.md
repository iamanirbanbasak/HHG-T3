# Milestone M08 — Candidate Filtering & Retrieval

## Objective

Implement `search.candidates` (allowlist filtering, URL normalisation, de-duplication) and the
bounded, hostile-input-safe candidate image fetch.

## Why This Milestone Exists

Lens returns a noisy mixture of news, stock, and aggregator pages. This milestone reduces that to
plausible social-media posts and retrieves their images so M09 can face-verify them.

## Requirements Covered

Owns: FR-014, FR-015, FR-016, FR-017, FR-053.

## Preconditions

M07 `PASS`.

## Inputs

`02` §3.6. `Config.social_domains`, `max_candidates`, `fetch_timeout_s`, `max_image_bytes`,
`fetch_concurrency`.

## Expected Repository State Before Starting

Lens integration green.

## Files To Create

```text
src/facechain/search/candidates.py
src/facechain/search/fetch.py
tests/test_candidates.py
tests/test_fetch.py
```

## Files To Modify

`src/facechain/config.py` — allowlist default if not already present.

## Files That Must Not Be Modified

`search/lens.py`, `search/uploader.py`, `face/`, `evidence.py`.

## Implementation Tasks

### Task 1 — Union and normalise

Union the crop-query and full-photo candidate sets, order-stable, first-seen wins (FR-014).
`normalise_url` strips query strings, fragments, and trailing slashes so the same post arriving
from both queries collapses to one candidate (FR-016).

### Task 2 — Social allowlist

Default from spec §4.6: `instagram.com`, `x.com`, `twitter.com`, `facebook.com`, `linkedin.com`,
`tiktok.com`, `threads.net`, `reddit.com`, `bsky.app`, `youtube.com`, plus a Mastodon heuristic
matching a `/@handle/` path segment. Configurable via `Config.social_domains`.

Match on registrable domain, not substring — `notinstagram.com.evil.co` must not pass.

### Task 3 — Bounded fetch

Per `09` §Untrusted input: https only, streaming size cap enforced **during** download not after,
connect and read timeouts, bounded redirects, content-type verified against actual bytes, SSRF
protection rejecting internal addresses.

Browser User-Agent and Referer headers to mitigate hotlink blocking (RK-03).

### Task 4 — Partial-failure semantics

A single candidate failing raises `CandidateFetchError`, which is **logged and skipped**; the run
continues with the remainder (FR-053). If *every* candidate fails, that is `NoVerifiedMatchError`
at M09 — the run completed and found nothing verifiable — not `CandidateFetchError`.

### Task 5 — Post text retrieval (AMB-06)

The bundle hashes `post_text_sha256` and M10's tamper demo mutates that file, so it must exist.
If Lens supplies only a page URL and a thumbnail, decide with the user how post text is obtained.
**Do not silently substitute the Lens `title` field for real post text** without recording it as
an `IMPLEMENTATION DECISION` — the tamper demo's honesty depends on what that file actually is.

## Technical Constraints

Concurrency bounded by `Config.fetch_concurrency` (default 4). **Never unbounded** (NFR-003).

## Interfaces / Contracts

`02` §3.6, exactly.

## Error Handling

Per `08` rows 9, 10, 11. Every fetch failure is typed, logged with context, and skipped.

## Performance Requirements

Concurrent fetching under the cap. Record per-candidate fetch latency and the skip rate — the
skip rate is the RK-03 early-warning signal.

## Accuracy Requirements

None. Filtering is by domain, never by content.

## Security Requirements

All of `09` §Untrusted input. Candidate images are downloaded from arbitrary hosts; treat every
byte as hostile.

## Tests To Add

### Unit Tests
Allowlist admits real social URLs and rejects news/stock/aggregator; substring-attack domain
rejected; de-duplication collapses query-string and trailing-slash variants; union is
order-stable.

### Integration Tests
Bounded fetch honours size cap and timeout; UA header present; concurrency never exceeds the cap.

### End-to-End Tests
Marked `e2e`: real Lens output → filtered → fetched.

### Regression Tests
Full suite.

### Failure Tests
403 skips that candidate and the run continues; timeout likewise; malformed image likewise;
oversized response aborted mid-stream; `file://` and internal addresses rejected.

### Performance Tests
Fetch latency and concurrency cap asserted.

### Accuracy Tests
None.

## Commands To Run

```bash
uv run pytest tests/test_candidates.py tests/test_fetch.py -v
uv run pytest -q
uv run facechain search --image tests/fixtures/face_single.jpg --show-candidates
```

## Acceptance Criteria

| # | Criterion | Evidence |
|---|---|---|
| 1 | Allowlist filters correctly | pytest |
| 2 | Substring-domain attack rejected | pytest |
| 3 | De-duplication works | pytest |
| 4 | Union order-stable | pytest |
| 5 | Size cap enforced during streaming | pytest |
| 6 | One failure skips one candidate only | pytest |
| 7 | Concurrency bounded | pytest |
| 8 | SSRF protections active | pytest |

## Exit Gate

```text
MILESTONE STATUS: PASS | BLOCKED | FAILED
```

## Failure Conditions

Unbounded concurrency. A single fetch failure aborting the run. Size cap applied after download
rather than during.

## Rollback Strategy

Revert `candidates.py` and `fetch.py`. M07 unaffected.

## Documentation Updates

README: allowlist and how to configure it; hotlink-blocking limitation (RK-03). `.agent-state`.

## Required Agent Report

Standard, plus skip rate observed against real candidates and the AMB-06 decision.

## Questions That Require User Input

**AMB-06** — post text provenance. Blocking for the tamper demo's meaning, not its mechanics.

## Definition of Done

Eight criteria met; AMB-06 resolved and recorded.
