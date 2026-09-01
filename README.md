# FaceChain

A pipeline that takes a face scan, finds matching content on social media through a genuine
reverse-image search, and anchors the discovered evidence on a blockchain as a tamper-evident
record that can later be independently re-verified.

**HH Goa 2026 — Shortlisting Task 3.**

---

## What it actually does

```
input photo
   │
   ├─ 1. DETECT ──────► face bbox + landmarks (SCRFD) → aligned 112×112 crop
   ├─ 2. ENCODE ──────► 512-d embedding (ArcFace w600k_r50), L2-normalised
   ├─ 3. SEARCH ──────► the ALIGNED FACE CROP is reverse-image-searched (Google Lens),
   │                    plus the full photo to widen recall; filtered to social domains
   ├─ 4. VERIFY ──────► every candidate image is INDEPENDENTLY re-detected and re-embedded,
   │                    then scored by cosine against the probe; below threshold → rejected
   ├─ 5. BUNDLE ──────► canonical-JSON evidence document → keccak256
   ├─ 6. ANCHOR ──────► FaceMatchRegistry.anchor() on-chain
   └─ 7. RE-VERIFY ───► hash read back FROM the chain, evidence recomputed from local
                        artifacts, the two compared side by side
```

### The design decision that matters

The naive version of this project reverse-image-searches the *whole photo*. Under that design the
face encoding is never used to find or filter anything — it is decorative, and the pipeline is an
image lookup wearing a face-recognition costume.

Here the embedding is load-bearing at **both** ends of the search: the query is the aligned face
crop, and every returned candidate has its own face detected and embedded and scored against the
probe. That converts a noisy set of visual matches into a ranked set of face matches with a real
numeric score, and filters the search provider's false positives.

`tests/test_pipeline.py::TestCandidateVerification` fails if that second half is removed.

## Install

```bash
uv venv --python 3.11
uv pip install -e ".[dev]"
cp .env.example .env      # then fill in your keys
```

First run downloads the ~300MB `buffalo_l` model pack to `~/.insightface`. Pre-warm before a demo.

## Usage

```bash
facechain scan   --image photo.jpg                       # detect + embed only
facechain search --image photo.jpg                       # + reverse search + face verification
facechain run    --image photo.jpg --network local       # full pipeline, anchors on-chain
facechain verify --record-id 0 --run-dir artifacts/run-x --network local
facechain verify --record-id 0 --run-dir artifacts/run-x --network local --tamper
facechain deploy --network base-sepolia
```

### Exit codes

| Code | Meaning |
|---|---|
| 0 | success (and the expected result of `verify --tamper`) |
| 1 | verification mismatch |
| 2 | no face detected |
| 3 | search provider error |
| 4 | no candidate cleared the threshold |
| 5 | blockchain error |

## Manual testing

### 1. Run the suite (no keys, no network needed)

```bash
uv run pytest -q --cov=src/facechain      # 184 tests, 80% coverage
```

### 2. Real face detection

```bash
facechain scan --image tests/fixtures/faces_multi.jpg   # 6 faces, det_score 0.92
facechain scan --image tests/fixtures/face_none.jpg     # NoFaceDetectedError, exit 2
```

### 3. Full evidence -> anchor -> verify -> tamper cycle

`--network local` is an **in-process** chain: its state does not survive between CLI
invocations, so `run` and `verify` cannot be separate commands against it. `selftest` performs
the whole cycle in one process:

```bash
# positive: same face -> cosine 1.0000 -> anchored -> MATCH -> tamper MISMATCH
facechain selftest \
  --probe tests/fixtures/faces_multi.jpg \
  --candidate tests/fixtures/faces_multi.jpg \
  --post-url "https://example.com/post/1"

# negative: different person -> cosine -0.0815 -> REJECT, nothing anchored, exit 4
facechain selftest \
  --probe tests/fixtures/faces_multi.jpg \
  --candidate tests/fixtures/face_other_person.jpg \
  --post-url "https://example.com/post/2"
```

**`selftest` bypasses search only** — you supply the candidate instead of it being discovered.
Detection, embedding, cosine, canonical hashing, the on-chain anchor and the `eth_call` read are
all real. It exists for manual testing and does not replace `run`, which is the graded pipeline.

Confirm the tamper demo left the originals untouched:

```bash
shasum -a 256 artifacts/run-*/probe.jpg artifacts/run-*/post_text.txt
```

### 4. What cannot be tested manually yet

`facechain run` needs a working search key (see Known limitations). Until then the discovery step
cannot be exercised live; the rest of the pipeline is covered by the commands above and by
`tests/test_end_to_end.py`.

## Which blockchain

**Solidity 0.8.24**, compiled with `py-solc-x` — no Foundry, no Hardhat, no Node toolchain.

- `--network local` — an in-process `eth-tester` chain. No RPC, no binary, no network. Used for
  development and the full test suite.
- `--network base-sepolia` — public testnet. Free faucet, ~2s blocks, Basescan explorer.

`FaceMatchRegistry` is deliberately minimal and **append-only**: no update path, no delete path,
no owner, no upgradeability. Mutability would defeat the purpose of the record. `postUrl` is
stored in cleartext so a reviewer can open the transaction and read the matched post.

## Re-verification and the tamper demo

`verify` does two independent things and compares them:

1. reads `evidenceHash` from the chain via `eth_call` — a real network read
2. rebuilds the bundle from `artifacts/<run-id>/`, **recomputing every digest from the stored
   source files**

It never reads a stored digest and compares it to itself, and it never re-fetches a hosted URL —
not the expired image-host crop, not the platform image. Verification keeps working indefinitely,
offline, with only the RPC endpoint reachable.

`verify --tamper` copies the artifacts to a scratch directory, flips **one byte of the post-text
source file**, and rebuilds. The changed text yields a different digest, a different bundle, and a
different hash — so it mismatches the unchanged on-chain record. The mutation happens at the
source-evidence level, not by editing a digest field; the original artifacts are byte-identical
afterwards.

## Tests

```bash
uv run pytest -q --cov=src/facechain      # 184 tests, 80% coverage, fully offline
uv run pytest -m e2e                      # requires real API keys
```

Unit and integration tests need no network. Chain tests use `eth-tester` in-process.

Several tests exist specifically to fail if the implementation becomes decorative:

| Test | Fails if |
|---|---|
| `test_candidates_are_independently_embedded` | candidates aren't individually embedded |
| `test_reads_from_chain` | the on-chain read is neutralised and verification still passes |
| `test_mutates_source_not_the_stored_digest` | `--tamper` edits a digest instead of source bytes |
| `test_originals_are_byte_identical_afterwards` | the tamper demo corrupts real evidence |
| `test_offline_verify_makes_no_http_calls` | verification reaches any URL but the RPC |
| `test_search_error` (paired) | a provider error is reported as an empty result |

## Known limitations

**Status: the search leg is not yet exercised live.** The imgbb upload hop is verified working
against the real API. The SerpAPI key currently configured is rejected (HTTP 401) and appears not
to be a SerpAPI key, so no live Google Lens query has run yet. Everything downstream of search is
built and tested; the end-to-end test substitutes the two provider calls and exercises real face
detection, real embedding, real hashing, and a real local chain.

**The threshold is not calibrated.** `tau = 0.45` is a conventional operating point for ArcFace,
carried from the design spec. It has not been validated against a labelled evaluation set. An
observed smoke check on the bundled multi-face fixture gives same-face cosine `1.0000` and
different-face cosine `0.0645`, which is wide separation — but two samples is not calibration, and
this is stated rather than implied otherwise.

**Similarity is a cosine score, never a percentage.** `similarityBps` on-chain is a raw cosine
encoding: 10000 means cosine 1.0, *not* "100% certain". The distinction is enforced by a test.

**A match is evidence, not identification.** A cosine above threshold is a ranked hypothesis. The
system does not identify anyone.

**The blockchain proves *when* a claim was recorded and that it has not changed since.** It does
not, and cannot, prove the claim is true. Anchoring a wrong match produces a permanent,
tamper-evident record of a wrong match. This is the distinction most projects in this space blur.

**Accuracy degrades** across pose, illumination, age gap, occlusion, and — well documented in the
literature — across demographic groups. A single cosine score carries no fairness guarantee.

**Absence of a match is not evidence of absence.** Reverse image search reaches only publicly
indexed content.

**Post text provenance.** Google Lens returns a page URL, title, and source rather than full post
body text. `post_text.txt` records what the provider actually returned, labelled as such. It is
not scraped post content.

**Deferred:** public testnet deployment (needs a funded wallet), threshold calibration (needs a
labelled set with a resolved consent basis), and performance optimisation (measurement only).

## Privacy

Face embeddings are biometric data. The evidence bundle stores only a **digest** of the embedding,
never the embedding itself. Raw artifacts stay local under `artifacts/` and are git-ignored.
Uploaded query crops carry a one-day expiry. Nothing biometric is persisted beyond what
verification requires.

Test fixtures are the sample images bundled with the `insightface` package — no scraped faces and
no private individuals.

## Project layout

```
src/facechain/
├── config.py          # the only module that reads os.environ
├── errors.py          # seven-class domain exception hierarchy
├── providers.py       # injection point for the two functions that call external services
├── evidence.py        # canonical JSON, SHA-256 artifact digests, keccak256 bundle hash
├── pipeline.py        # the load-bearing candidate verification loop
├── verify.py          # on-chain read + independent local recompute
├── face/              # detect, embed, similarity
├── search/            # uploader, lens, candidates, fetch
├── chain/             # compile, deploy, registry
└── cli.py             # six commands (the only UI; no website required)
```

Documentation of the build system used to produce this lives in `agent-prompts/`.
