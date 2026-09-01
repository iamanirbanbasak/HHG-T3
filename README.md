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

## Search backends

The pipeline supports two, selected with `--provider` or `SEARCH_PROVIDER`.

| | `google_lens` (default) | `facecheck` |
|---|---|---|
| What it does | matches **images** already in Google's index | runs **face recognition** over crawled social images |
| Finds a face never published as this exact image | no | yes |
| Needs a public image host | yes (imgbb hop) | no, direct upload |
| Candidate images | fetched by URL, may 403 | inline base64, no fetch |
| Cost | SerpAPI free tier | paid; `demo` mode is free |

**This distinction matters and is easy to get wrong.** Google Lens is not a face search engine.
Photograph yourself now and Lens has nothing to match, because that image has never been indexed
— measured live: 120 candidates, 20 social, 19 face-verified, best cosine 0.2923, all rejected.
That is the pipeline working correctly on an input with nothing findable behind it.

For "scan a face, find that person's accounts", use `facecheck`:

```bash
facechain run --capture --provider facecheck --network local
```

`FACECHECK_DEMO=1` is the default so a misconfigured run cannot silently spend credits.

**The provider's own score is never the verdict.** FaceCheck returns a 0–100 confidence; it is
recorded as metadata only. Every candidate is still independently detected, embedded, and
cosine-scored against the probe by this pipeline. The provider proposes; the embedding disposes.

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

**The search leg now runs live, but no genuine match has been demonstrated yet.** A real Google
Lens query against a face crop returned 60 candidates, 7 of them on social-media domains. All 7
were then fetched and independently face-verified, and **all 7 were rejected** -- the best scored
cosine 0.2629 against a 0.45 threshold. They were visually-plausible false positives, not the
subject.

That is the pipeline behaving correctly rather than failing: it is exactly what candidate face
verification exists to catch, and it is the difference between this design and one that would
have reported the top Lens hit as a match. But it means an end-to-end run producing a *verified*
match still needs a demo subject whose face is well indexed at usable resolution. The test used a
112x112 pre-aligned crop, which is small and context-free -- poor conditions for reverse image
search.

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

---

# Getting started (handover)

Everything below is what you need to go from a fresh clone to a working run. Read it top to
bottom the first time; it takes about 15 minutes, most of it waiting on a model download.

## 0. What this actually is, in three sentences

You give it a face. It computes a 512-d embedding, reverse-image-searches the aligned face crop,
then **independently re-detects and re-embeds every candidate the search returns** and scores each
one by cosine similarity against the probe. Whatever survives a threshold gets hashed into a
canonical evidence bundle, anchored on a blockchain, and can later be recomputed from local files
and compared against the on-chain record.

The second step is the whole point. Without it, the face encoding would be decorative and the
project would just be an image lookup. Read `pipeline.verify_candidates` first — it is the part a
reviewer will scrutinise.

## 1. Prerequisites

| Need | Why | Check |
|---|---|---|
| Python 3.11 | the pinned runtime | `python3 --version` |
| `uv` | dependency management | `uv --version`, else `brew install uv` |
| ~1 GB free disk | face models + solc | — |
| A webcam | only for `--capture` | optional |

Apple Silicon and Intel macOS both work. Linux should work; nothing is macOS-specific except
HEIC decoding and the camera backend.

## 2. Install

```bash
git clone https://github.com/iamanirbanbasak/HHG-T3.git
cd HHG-T3
uv venv --python 3.11
uv pip install -e ".[dev]"
```

## 3. Keys

```bash
cp .env.example .env
```

Then fill in `.env`. **`.env` is git-ignored and must stay that way.**

| Key | Needed for | Where to get it |
|---|---|---|
| `SERPAPI_KEY` | reverse image search | serpapi.com/manage-api-key — free tier is 250/month. A real key is **64 hex characters with no prefix**; anything shaped like `live_...` is a different service and will 401. |
| `IMGBB_KEY` | hosting the crop so Lens can fetch it | api.imgbb.com — free |
| `FACECHECK_KEY` | optional, real face search | facecheck.id — paid, but `FACECHECK_DEMO=1` costs no credits |
| `PRIVATE_KEY` | optional, public testnet | a **throwaway** wallet with Base Sepolia faucet ETH only |

You can run everything except the search step with no keys at all.

## 4. First run — no keys, no network

```bash
uv run pytest -q                    # ~220 tests, fully offline
```

If that is green, the face models, the Solidity toolchain and the local chain all work on your
machine. This is the fastest way to know the environment is sound.

**First run downloads ~300 MB of face models** to `~/.insightface` and fetches `solc 0.8.24`.
Expect several minutes once, then it is cached. Pre-warm before any demo.

## 5. Prove the chain half works, still with no keys

```bash
uv run facechain selftest \
  --probe tests/fixtures/faces_multi.jpg \
  --candidate tests/fixtures/faces_multi.jpg \
  --post-url "https://example.com/p/1"
```

You should see cosine `1.0000` → anchored → **MATCH** → **MISMATCH** on the tamper demo.
Then the negative path:

```bash
uv run facechain selftest \
  --probe tests/fixtures/faces_multi.jpg \
  --candidate tests/fixtures/face_other_person.jpg \
  --post-url "https://example.com/p/2"
```

Cosine ≈ `-0.08` → rejected → exit 4, nothing anchored.

`selftest` bypasses **search only**; you supply the candidate. Everything else is real. It exists
because `--network local` is an in-process chain whose state does not survive between CLI
invocations, so `run` and `verify` cannot be separate commands against it.

## 6. Full pipeline, with keys

```bash
uv run facechain run --image me.jpg --network local        # from a file
uv run facechain run --capture --network local             # from the webcam
```

macOS will ask for camera permission the first time. If it fails with "not authorized", grant
Camera to your terminal in **System Settings → Privacy & Security → Camera** and retry.

## 7. Web UI (optional)

```bash
uv run facechain serve       # http://127.0.0.1:8000
```

Localhost only, CSRF-protected, and image paths are confined to the project directory. It drives
the same functions as the CLI rather than reimplementing them.

## 8. Exit codes

Scriptable, and asserted by tests.

| 0 | success (also the expected result of `verify --tamper`) |
|---|---|
| 1 | verification mismatch |
| 2 | no face detected |
| 3 | search provider error |
| 4 | no candidate cleared the threshold |
| 5 | blockchain error |

## 9. Where to look in the code

```
src/facechain/
├── pipeline.py        ← START HERE. verify_candidates is the core claim.
├── evidence.py        ← canonical JSON + hashing. Determinism lives or dies here.
├── verify.py          ← on-chain read vs independent local recompute
├── providers.py       ← injection point for the two functions that call outward
├── config.py          ← the ONLY module that reads os.environ
├── errors.py          ← seven domain exceptions
├── face/              ← detect, embed, similarity
├── search/            ← lens, facecheck, uploader, candidates, fetch
├── chain/             ← compile, deploy, registry
└── cli.py             ← presentation only, no business logic
```

Design rules enforced by tests, not just convention:

- dependency direction is one-way (`test_import_graph.py`)
- only `config.py` reads the environment
- no social-media URL literal exists in `src/` (`test_no_hardcoding.py`)
- provider fakes live in `tests/fakes.py`, never in `src/`, so there is no stub to delete

## 10. Gotchas that cost time

**Do not mock the thing you are testing.** Two real bugs shipped green because of this: `httpx.stream`
was mocked while the real call used an argument that does not exist there, and `CliRunner` runs
in-process so it never saw a native-teardown crash that replaced exit code 4 with 134. Prefer
`MockTransport` and real subprocesses.

**Never regenerate `tests/fixtures/golden_hash.txt` to make a red test pass.** If it changes, find
out why. It has legitimately changed exactly once, when the evidence schema changed on purpose.

**Google Lens is not a face search engine.** It matches images already in Google's index. A photo
taken just now has never been indexed, so it will find nothing — that is correct behaviour, not a
bug. Use an already-public photo, or the `facecheck` provider.

**Never commit face images.** `me.jpg`, `capture.jpg` and `artifacts/` are git-ignored. Captured
faces are biometric data.

## 11. Current status

| Working | Not done |
|---|---|
| face detection, embedding, similarity | public testnet deploy (needs a funded wallet) |
| evidence hashing + golden tests | threshold calibration (needs a consented labelled set) |
| contract, anchor, verify, tamper | performance optimisation (measurement only) |
| Lens search, candidate face verification | screen recording |
| CLI, camera capture, web UI | |

Verified live: a real Lens query returned 120 candidates, 20 on social domains, and the two
genuine matches scored 0.8902 and 0.7770 while everything else fell to 0.2534 and below.

**Open question worth resolving before recording:** the pipeline anchors only the single
highest-scoring candidate. In that live run the top two both cleared threshold, and identity was
confirmed for the second, not the first. If the top scorer is ever a false positive, the current
rule anchors the wrong record. Surfacing all above-threshold candidates for a human decision is
probably the more honest design, given the system produces evidence rather than identification.


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
