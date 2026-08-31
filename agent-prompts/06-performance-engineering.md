# 06 — Performance Engineering

**Principle: measure, do not guess.** No optimisation lands without a before/after number.

Owned NFRs: NFR-001, NFR-002, NFR-003. Owning milestone: M13.

## What to measure

```text
startup time
model loading time
face detection latency
embedding latency
upload latency
search latency
candidate fetch latency
candidate embedding latency
blockchain transaction latency
verification latency
```

Track p50 / p95 / p99 where the sample size makes them meaningful. With fewer than ~20 samples,
report p50 and max, and say so — a p99 from 5 samples is noise dressed as rigour.

## Harness

`bench/run_bench.py` emits a table per stage and writes `bench/latest.json`. It runs against
mocked providers by default so numbers are comparable run to run; a `--live` flag measures the
real network path for the M17 rehearsal.

## Expected cost order

1. **Model load** — hundreds of ms to seconds, once per process
2. **Candidate fetch** — network-bound, the dominant cost at scale, parallelisable
3. **Candidate embedding** — CPU-bound, ~50ms per face
4. **Lens round-trips** — network-bound, exactly two per run
5. **Anchor transaction** — chain-bound, ~2s on Base Sepolia
6. **Detection / embedding of the probe** — single-digit percentage of total

## Permitted optimisations

- model warm-up and reuse (load once per process — NFR-002)
- HTTP connection pooling
- explicit timeouts everywhere
- concurrent candidate fetching **under a bounded cap** (`Config.fetch_concurrency`, default 4)
- image size limits before decode (`Config.max_image_bytes`)
- avoiding repeated embeddings of the same candidate within a run
- in-run caching keyed by normalised URL
- avoiding redundant serialisation

## Forbidden optimisations

- **unbounded concurrency** — NFR-003, and a fast way to get rate-limited mid-demo
- **removing verification** — deleting the candidate-embedding step makes the run faster and the
  project fraudulent (HC-03)
- **reducing accuracy without documenting the trade-off** — a raised threshold that drops recall
  is a decision, not a speedup
- lowering candidate count below what the threshold needs to find a match

## Gate

M13 passes when `bench/latest.json` exists, the critical path is characterised, and every
optimisation applied has a recorded before/after. If no optimisation was needed, that is a valid
M13 outcome: record the measurements and say so.

**M13 is the first candidate to drop under deadline pressure (RK-10).** If dropped, measurement
still happens; only optimisation is deferred. Record the numbers regardless.
