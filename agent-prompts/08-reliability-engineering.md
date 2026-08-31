# 08 — Reliability Engineering

Owned NFR: NFR-006. Owning milestone: M14.

## The distinction that matters most

```text
provider failure  ≠  legitimate empty result
```

A broken API key, a 500, or a timeout is **not** "we searched and found nothing". Conflating them
makes a misconfiguration look like a real negative result — which, on a project whose entire
claim is that the search is genuine, is the most damaging bug available (FR-052, HC-17).

`search.lens` raises `SearchProviderError` on any non-2xx or malformed body. It returns `[]` only
when the provider successfully reported no matches. The CLI renders these differently and exits
with different codes.

## Required failure tests

Every row gets a test in `tests/reliability/`.

| # | Failure | Expected behaviour |
|---|---|---|
| 1 | no face in probe image | `NoFaceDetectedError`, exit 2, no embedding fabricated |
| 2 | multiple faces | highest `det_score` selected, count recorded, run continues |
| 3 | malformed image | typed error, no crash, no partial artifact directory |
| 4 | provider timeout | `SearchProviderError`, distinct from empty |
| 5 | provider 4xx | `SearchProviderError`, message names the status |
| 6 | provider 5xx | `SearchProviderError`, message names the status |
| 7 | invalid API key | `SearchProviderError`, **key value never appears in the message or log** |
| 8 | empty search results | `[]`, exit 4 via `NoVerifiedMatchError`, reported as a legitimate negative |
| 9 | candidate image 403 | `CandidateFetchError`, that candidate skipped, run continues |
| 10 | candidate image timeout | as above |
| 11 | malformed candidate image | as above |
| 12 | no verified candidate | `NoVerifiedMatchError`, nothing anchored, exit 4 |
| 13 | RPC failure | `ChainError`, exit 5, no partial receipt written |
| 14 | transaction revert | `ChainError` carrying the revert reason |
| 15 | missing contract address | `ChainError` with actionable message |
| 16 | corrupted artifact | `EvidenceIntegrityError` on verify, exit 1 |
| 17 | missing artifact | typed error naming the missing file, not a `KeyError` |
| 18 | tampered artifact | `EvidenceIntegrityError`, MISMATCH displayed |

## Partial-failure semantics

One candidate failing must never fail the run. The pipeline logs the skip, records the count, and
continues with the remainder. If *every* candidate fails to fetch, that is
`NoVerifiedMatchError`, not `CandidateFetchError` — the run completed and found nothing
verifiable.

## No silent handling

Every `except` either logs with a stack trace and re-raises, or converts to a typed domain error
carrying context. A bare `except:` or a swallowed exception is a review failure. No exception is
caught to make a demo look smoother.

## Gate

M14 passes when all 18 rows have passing tests and the provider-failure-vs-empty distinction is
demonstrated by two tests that differ only in the mocked response.
