# Face Identification & Blockchain Verification Pipeline — Design

- **Project**: HH Goa 2026 Shortlisting Task 3
- **Date**: 2026-08-31
- **Deadline**: 2026-09-07, 23:59
- **Status**: Approved — ready for implementation planning
- **Working name**: `facechain`

---

## 1. Problem

Build a pipeline that takes a face scan as input, identifies matching content on the web or
social media, and verifies that discovered data using a blockchain — end to end.

The task states three hard technical requirements, one hard deliverable constraint, and two
submission artifacts:

| # | Requirement | Where it is satisfied |
|---|---|---|
| R1 | Detect and encode a face from an input image | §4.1 Detect, §4.2 Encode |
| R2 | Use the face to search the web and find at least one **real** matching social media post, via a **genuine search step** — not a hardcoded or pre-picked result | §4.5–4.6 Search, §4.7 Face verification |
| R3 | Upload the post (or a hash/fingerprint) to a blockchain to create a verifiable, tamper-evident record, and demonstrate **re-verifying** the data against the on-chain record | §6 Contract, §7 Re-verification |
| C1 | No website required | CLI-only; see §4.10, §8 |
| C2 | GitHub repo with README covering what it does, how to run it, which blockchain, and known limitations | §9 Repository layout, §15 Ethics & limitations |
| S1 | Screen recording of the pipeline working end to end | §12 Day 6 |
| S2 | Submission form, **no resubmissions** | §12 Day 7 |

### Non-goals

- No web frontend, no hosted service, no auth. The task explicitly waives this.
- No production-grade identity claims. The output is *evidence of a probable match*, not an
  identification. See §15.
- No attempt to search platforms that require authenticated scraping (private accounts,
  logged-in-only surfaces).

---

## 2. The key design decision

The naive pipeline is: photo → reverse image search → post → hash it. **This design is rejected.**

Under it, the face encoding required by R1 is never actually used to find or filter anything —
the search is a whole-image lookup and the embedding is decorative. A reviewer comparing the
implementation against R1 and R2 would correctly observe that no face matching occurs.

**The accepted design makes the embedding load-bearing at both ends of the search:**

1. The **query** sent to reverse image search is the *aligned face crop*, not the original photo.
2. Every **candidate** returned by search has its own image fetched, its face detected and
   embedded, and is scored by cosine similarity against the probe embedding. Candidates below
   threshold are discarded.

This converts a noisy set of visual matches into a ranked set of face matches with a numeric
confidence score. That score is displayed in the demo, written into the evidence bundle, and
recorded on-chain. It also filters reverse-image-search false positives, which is the practical
reason to do it regardless of the grading rubric.

---

## 3. Architecture

```
input photo (JPEG/PNG)
   │
   ├─ 1. DETECT ──────► face bbox + 5-point landmarks (SCRFD)
   │                    → aligned 112x112 crop                          [R1]
   │
   ├─ 2. ENCODE ──────► probe embedding: 512-d ArcFace, L2-normalised   [R1]
   │
   ├─ 3. SEARCH ──────► host crop at a public URL (imgbb)
   │                    SerpAPI → Google Lens → visual matches
   │                    union with a second query on the full photo
   │                    filter to social-media domain allowlist         [R2]
   │
   ├─ 4. VERIFY FACE ─► per candidate: fetch image → detect → encode
   │                    cosine(probe, candidate) >= tau → keep
   │                    rank descending; top match wins                 [R2]
   │
   ├─ 5. BUNDLE ──────► canonical-JSON evidence document
   │                    evidenceHash = keccak256(canonical bytes)
   │
   ├─ 6. ANCHOR ──────► FaceMatchRegistry.anchor(hash, postUrl, simBps)
   │                    Base Sepolia (or local eth-tester)              [R3]
   │
   └─ 7. RE-VERIFY ───► read hash FROM CHAIN via eth_call
                        recompute from bundle on disk, compare          [R3]
                        `verify --tamper` mutates one byte → MISMATCH
```

Steps 1–6 run as `facechain run`. Every step is also individually invocable so a single leg can
be re-run or re-recorded without repeating the whole pipeline.

---

## 4. Component design

Each component below is independently testable, communicates through a plain-data interface, and
depends only on what is listed.

### 4.1 `face.detect`

- **Does**: Locates faces in an image and returns aligned crops.
- **Interface**: `detect_faces(image: np.ndarray) -> list[DetectedFace]` where `DetectedFace`
  carries `bbox`, `landmarks`, `det_score`, and `aligned: np.ndarray` (112x112x3).
- **Depends on**: InsightFace `buffalo_l` SCRFD model, numpy.
- **Behaviour**: If the image contains multiple faces, the highest-scoring detection is the probe
  and this is recorded in the bundle. If zero faces are detected, raises `NoFaceDetectedError`.

### 4.2 `face.embed`

- **Does**: Turns an aligned crop into a 512-d L2-normalised embedding.
- **Interface**: `embed(aligned: np.ndarray) -> np.ndarray` (shape `(512,)`, float32).
- **Depends on**: InsightFace `buffalo_l` ArcFace recognition model, onnxruntime.

### 4.3 `face.similarity`

- **Does**: Scores two embeddings.
- **Interface**: `cosine(a: np.ndarray, b: np.ndarray) -> float`, range `[-1.0, 1.0]`.
- **Depends on**: numpy only. Pure function, trivially unit-tested.

### 4.4 `search.uploader`

- **Does**: Publishes a local image at a temporary public HTTPS URL, because the Google Lens
  endpoint accepts a URL and not raw bytes.
- **Interface**: `upload(path: Path) -> str`.
- **Depends on**: imgbb API (`IMGBB_KEY`), httpx.
- **Behaviour**: Uploads are created with imgbb's expiry parameter set to 1 day, so demo crops do
  not persist indefinitely. Raises `SearchProviderError` on non-2xx.

### 4.5 `search.lens`

- **Does**: Runs a reverse image search and returns raw candidates.
- **Interface**: `search(image_url: str) -> list[Candidate]` where `Candidate` carries
  `page_url`, `image_url`, `title`, `source`.
- **Depends on**: SerpAPI `google_lens` engine (`SERPAPI_KEY`), httpx.
- **Behaviour**: Errors from the provider raise `SearchProviderError`; they are never swallowed
  into an empty result, because an empty result and a failed call must be distinguishable.

### 4.6 `search.candidates`

- **Does**: Filters and de-duplicates raw candidates down to plausible social-media posts.
- **Interface**: `filter_social(cands: list[Candidate]) -> list[Candidate]`.
- **Depends on**: a configurable domain allowlist. Default:
  `instagram.com`, `x.com`, `twitter.com`, `facebook.com`, `linkedin.com`, `tiktok.com`,
  `threads.net`, `reddit.com`, `bsky.app`, `youtube.com`, plus any host matching a Mastodon
  instance heuristic (`/@handle/` path segment).
- **Behaviour**: De-duplicates by normalised `page_url`. Preserves provider ordering.

### 4.7 `pipeline`

- **Does**: Orchestrates steps 1–5 and returns an `EvidenceBundle`.
- **Interface**: `run(image: Path, cfg: Config) -> EvidenceBundle`.
- **Depends on**: all of `face.*` and `search.*`, plus `evidence`.
- **Behaviour**: Issues two Lens queries — the aligned crop and the full photo — and unions the
  candidate sets before filtering. The crop query is primary; the full-photo query exists purely
  to widen recall (see R2 in §14). Face verification in step 4 is the arbiter for both, so the
  embedding remains load-bearing regardless of which query surfaced a candidate.
  If no candidate clears `tau`, raises `NoVerifiedMatchError` — the pipeline does **not**
  fabricate or downgrade a match.

### 4.8 `evidence`

- **Does**: Serialises the bundle canonically and hashes it.
- **Interface**: `canonicalise(bundle: dict) -> bytes`, `evidence_hash(bundle: dict) -> bytes32`.
- **Depends on**: stdlib `json`, `hashlib`, `eth_utils.keccak`.
- **Behaviour**: Canonical form is
  `json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")`.
  This is not optional — without stable key ordering and separators, re-verification fails
  spuriously on serialisation differences rather than on tampering.

### 4.9 `chain.compile` / `chain.deploy` / `chain.registry`

- **Does**: Compiles the Solidity source, deploys it, and wraps the contract calls.
- **Interface**: `compile_registry() -> tuple[abi, bytecode]`,
  `deploy(w3, acct) -> address`,
  `Registry.anchor(bundle_hash, post_url, sim_bps) -> (record_id, tx_hash)`,
  `Registry.get(record_id) -> Record`.
- **Depends on**: `py-solc-x` (pinned solc 0.8.24), `web3.py`.
- **Behaviour**: `Registry` is provider-agnostic; the same object works against `eth-tester` and
  Base Sepolia. Network selection happens once, in `Config`.

### 4.10 `cli`

- **Does**: Presents the pipeline. The recording is the product's only UI, so this matters.
- **Commands**: `scan`, `search`, `anchor`, `verify`, `run`, `deploy`.
- **Depends on**: Typer, Rich.

---

## 5. Data model

### 5.1 Evidence bundle (`hhg-t3/evidence/v1`)

```json
{
  "schema": "hhg-t3/evidence/v1",
  "probe": {
    "image_sha256": "<hex>",
    "bbox": [x, y, w, h],
    "det_score": 0.94,
    "embedding_sha256": "<hex>",
    "faces_detected": 1,
    "models": {
      "detector": "scrfd_10g_bnkps",
      "embedder": "arcface_r100_glint360k",
      "pack": "buffalo_l"
    }
  },
  "search": {
    "provider": "serpapi/google_lens",
    "queried_at": "2026-09-05T12:00:00Z",
    "query_image_sha256": "<hex>",
    "queries": ["face_crop", "full_photo"],
    "n_candidates": 27,
    "n_social": 9,
    "n_face_verified": 3
  },
  "match": {
    "post_url": "https://www.instagram.com/p/...",
    "platform": "instagram",
    "author_handle": "...",
    "image_url": "...",
    "image_sha256": "<hex>",
    "post_text_sha256": "<hex>",
    "captured_at": "2026-09-05T12:00:04Z"
  },
  "verification": {
    "cosine_similarity": 0.7123,
    "threshold": 0.45,
    "passed": true
  }
}
```

The bundle records **one** match: the highest-scoring candidate that cleared threshold. The count
of other verified candidates is attested by `search.n_face_verified`. Anchoring every match was
considered and cut — nothing in the task requires it and it multiplies gas and demo time.

Raw artifacts (probe image, aligned crop, candidate image, post text) are written alongside the
bundle under `artifacts/<run-id>/` so re-verification can recompute every digest from source.

### 5.2 Hashing

- Individual artifact digests inside the bundle: **SHA-256**, lowercase hex, no prefix.
- The on-chain anchor: **keccak256** of the canonical bundle bytes, as a Solidity-native
  `bytes32`.

Two algorithms is deliberate, not an inconsistency: SHA-256 is the natural choice for file
digests, keccak256 is the EVM-native word. Each is used in exactly one place.

### 5.3 Similarity encoding

`similarityBps = max(0, min(10000, round(cosine * 10000)))`, stored as `uint16`. Cosine can be
negative for non-matching faces; clamping at zero keeps the on-chain type unsigned and loses no
information, because anything anchored has already cleared a positive threshold.

`similarityBps` is a **raw cosine encoding, not a probability or a confidence percentage**. A
value of 10000 means cosine 1.0, not "100% certain". This matters because the on-chain value is
the one artifact a reviewer sees without the README beside it, and reading it as a confidence
percentage would assert exactly the claim §15 disclaims. The README and the CLI both label it as
cosine, never as a percentage.

### 5.4 Threshold

`tau` defaults to **0.45** cosine, configurable via `--threshold`. This is a conventional
operating point for ArcFace `r100` trained on glint360k. It will be sanity-checked during Day 3–4
against a small labelled set (approximately 10 same-identity pairs and 10 different-identity
pairs assembled from public images) and the chosen value plus its observed separation recorded in
the README. The default is not treated as calibrated until that check runs.

---

## 6. Smart contract

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

contract FaceMatchRegistry {
    struct Record {
        bytes32 evidenceHash;
        string  postUrl;
        uint16  similarityBps;
        uint64  timestamp;
        address submitter;
    }

    Record[] private _records;

    event MatchAnchored(
        uint256 indexed id,
        bytes32 indexed evidenceHash,
        string  postUrl,
        uint16  similarityBps,
        address indexed submitter
    );

    function anchor(bytes32 evidenceHash, string calldata postUrl, uint16 similarityBps)
        external returns (uint256 id)
    {
        require(evidenceHash != bytes32(0), "empty hash");
        require(bytes(postUrl).length > 0, "empty url");
        id = _records.length;
        _records.push(Record({
            evidenceHash:  evidenceHash,
            postUrl:       postUrl,
            similarityBps: similarityBps,
            timestamp:     uint64(block.timestamp),
            submitter:     msg.sender
        }));
        emit MatchAnchored(id, evidenceHash, postUrl, similarityBps, msg.sender);
    }

    function get(uint256 id) external view returns (Record memory) { return _records[id]; }

    function verify(uint256 id, bytes32 candidate) external view returns (bool) {
        return _records[id].evidenceHash == candidate;
    }

    function count() external view returns (uint256) { return _records.length; }
}
```

Design notes:

- The contract is deliberately minimal. The chain's role is a tamper-evident timestamp, not a
  database. Records are append-only and there is no update or delete path — mutability would
  defeat the entire purpose.
- `postUrl` is stored in cleartext rather than hashed. It costs gas, but it means a reviewer can
  open the transaction on Basescan and read the matched post directly. That legibility is worth
  more than the gas on a testnet.
- `verify` exists on-chain for completeness, but the CLI's re-verification deliberately uses
  `get()` and compares locally, so the comparison is visible to the viewer rather than hidden
  inside a boolean returned by the chain.

### Networks

| Name | Provider | Purpose |
|---|---|---|
| `local` | `eth-tester` (in-process EVM) | Development, tests, offline demo fallback |
| `base-sepolia` | Base Sepolia RPC | Public testnet deploy shown in the recording |

Base Sepolia is chosen for free faucet access, ~2s blocks, and a public Basescan explorer link.
Switching to Ethereum Sepolia or Polygon Amoy is a one-line `Config` change; nothing in the code
is Base-specific.

---

## 7. Re-verification and the tamper demonstration

R3 requires demonstrating re-verification against the on-chain record. The failure mode to design
against is a verifier that loads the local evidence file for *both* sides of the comparison and
compares it to itself, which proves nothing and is an easy accident.

`facechain verify --record-id N` must therefore:

1. Fetch `Record.evidenceHash` from the chain via `eth_call` — a real network read.
2. Rebuild the bundle from the raw artifacts in `artifacts/<run-id>/` — recomputing
   `probe.image_sha256`, `match.image_sha256`, and `match.post_text_sha256` from the stored
   source files — then canonicalise and hash the result.
3. Print both, side by side, with the block number and network.

**Recomputation reads local disk only.** No digest is ever recomputed by re-fetching a hosted
URL: not the imgbb-hosted query crop (which expires after one day, per §4.4), and not the
candidate's image on the social platform (which may 403 or be deleted at any time). Verification
must keep working indefinitely after the recording, on a laptop with no network access to
anything except the RPC endpoint. This is the only external read in step 1, and it is the one
read that has to be external.

```
on-chain    0x8f3a...c21d   (block 12,847,392 - Base Sepolia)
recomputed  0x8f3a...c21d
MATCH  record intact
```

`facechain verify --record-id N --tamper` performs the same on-chain read, but first mutates a
single byte **of the stored post-text source file** in `artifacts/<run-id>/`, then rebuilds the
bundle normally. The altered text yields a different `match.post_text_sha256`, which yields a
different bundle, which yields a different hash:

```
on-chain    0x8f3a...c21d
recomputed  0x1b7e...9004
MISMATCH  evidence has been altered
```

The distinction matters and is deliberate: `--tamper` alters the **evidence at its source** and
lets the digest change propagate up, rather than editing the digest inside the bundle directly.
Only the former demonstrates the chain catching a real alteration to real evidence; the latter
would be a self-referential trick that a reviewer reading the code would rightly discount. The
mutation is applied to a scratch copy of the artifact directory so the original run stays intact.

`--tamper` is a first-class command surface rather than something narrated over a static screen,
because it is the only part of the demo that actually proves tamper-evidence.

---

## 8. Tech stack

| Layer | Choice | Rationale |
|---|---|---|
| Language | Python 3.11, `uv` | One language end to end; `uv` already present on the machine |
| Face detection + encoding | InsightFace `buffalo_l` (SCRFD + ArcFace r100) on onnxruntime | Prebuilt arm64 wheels; 512-d embeddings; fully local; no API key; ~50ms/face |
| Image I/O | `opencv-python-headless`, `numpy`, `Pillow` | headless avoids macOS GUI dylib issues |
| HTTP | `httpx` | Timeouts and retries are first-class |
| Reverse image search | SerpAPI `google_lens` | Official structured endpoint; no scraping, no anti-bot fight, no ToS problem |
| Temporary image hosting | imgbb API | Lens requires a public URL for the query image |
| Contract language | Solidity 0.8.24 | — |
| Contract toolchain | `py-solc-x` | No Foundry, no Hardhat, no Node toolchain. `solc` is already installed |
| Chain client | `web3.py` | Identical code path for local and testnet; provider swap only |
| Local chain | `eth-tester` via `web3[tester]` | In-process EVM, no external binary, instant test runs |
| Public chain | Base Sepolia | Free faucet, fast blocks, Basescan explorer link |
| CLI / presentation | Typer + Rich | The recording is the only UI; Rich tables and progress make it legible |
| Tests | pytest | Per project standards |

### Rejected alternatives

- **`face_recognition` / dlib** — source builds are unreliable on arm64 and its 128-d encodings
  are measurably weaker than ArcFace. Rejected on both robustness and quality.
- **Foundry or Hardhat** — a second toolchain and install for a single 40-line contract that
  `py-solc-x` compiles from the already-installed `solc`. Rejected on deadline cost.
- **Merkle tree over bundle fields** — enables selective disclosure, which nothing in the task
  requires. A single `bytes32` over the canonical bundle is sufficient. Rejected as YAGNI.
- **IPFS pinning of the bundle** — genuinely nice, but adds a third API key and a third failure
  mode on a 7-day clock. Moved to §16 future work.
- **Second search lane: crawl Bluesky/Mastodon and build a local face index** — considered at
  length and cut. If the subject is only findable because we seeded the corpus, the search is
  circular and arguably violates R2's "not hardcoded" clause; it is also slow on camera and
  doubles the build. Moved to §16 future work.
- **PimEyes or direct Yandex/Google scraping** — ToS violations and active anti-bot measures.
  Rejected.

---

## 9. Repository layout

```
hhg-t3-face-chain/
|- README.md                    # what it does, how to run, which chain, limitations
|- pyproject.toml               # uv-managed
|- .env.example                 # SERPAPI_KEY, IMGBB_KEY, RPC_URL, PRIVATE_KEY, CONTRACT_ADDRESS
|- .gitignore                   # .env, artifacts/ (except artifacts/sample/), models/
|- contracts/
|  \- FaceMatchRegistry.sol
|- src/facechain/
|  |- cli.py                    # typer: scan | search | anchor | verify | run | deploy
|  |- config.py                 # env + flags -> Config; network selection
|  |- errors.py                 # exception hierarchy
|  |- pipeline.py               # orchestrates steps 1-5
|  |- evidence.py               # canonical json + hashing
|  |- face/
|  |  |- detect.py
|  |  |- embed.py
|  |  \- similarity.py
|  |- search/
|  |  |- uploader.py
|  |  |- lens.py
|  |  \- candidates.py
|  \- chain/
|     |- compile.py
|     |- deploy.py
|     \- registry.py
|- tests/
|  |- test_similarity.py
|  |- test_evidence.py          # canonical-JSON golden file
|  |- test_candidates.py
|  |- test_registry.py          # eth-tester integration
|  |- test_verify_tamper.py
|  |- test_pipeline_no_match.py
|  |- test_search_error.py
|  \- fixtures/
\- artifacts/
   \- sample/                   # one committed sample run for README reference
```

### Configuration

All secrets come from `.env` (git-ignored); `.env.example` documents every key with no values.
`Config` is constructed once in `cli.py` and passed down — no module reads `os.environ` directly,
so tests can construct a `Config` without touching the environment.

---

## 10. Error handling

Following project standards: a domain exception hierarchy, specific exception types, no silent
failures, and `try/except` at boundaries rather than deep in business logic.

```
FaceChainError                  # base
|- NoFaceDetectedError          # step 1: probe image has no detectable face
|- SearchProviderError          # steps 3: SerpAPI or imgbb returned an error
|- CandidateFetchError          # step 4: candidate image could not be retrieved
|- NoVerifiedMatchError         # step 4: zero candidates cleared tau
|- ChainError                   # steps 6-7: RPC, revert, or receipt failure
\- EvidenceIntegrityError       # step 7: recomputed hash != on-chain hash
```

Two rules that matter specifically here:

- A provider error must never collapse into "no results". `SearchProviderError` and an empty
  candidate list are different outcomes and the CLI reports them differently — conflating them
  would make a broken API key look like a legitimate negative result.
- `CandidateFetchError` on a single candidate is logged and that candidate is skipped; the run
  continues with the remainder. Failure to fetch one image is not failure of the pipeline.

`EvidenceIntegrityError` is a successful outcome of `verify --tamper` and an exit-code-1 failure
of plain `verify`. The CLI distinguishes these.

---

## 11. Testing strategy

Target 80% coverage. External services are mocked; internal modules are not.

| Test | Type | What it pins down |
|---|---|---|
| `test_similarity` | unit | Cosine is correct, symmetric, and bounded; identical vectors score 1.0 |
| `test_evidence` | unit, golden file | Canonical JSON is byte-stable across key reordering and across runs; the golden hash does not drift |
| `test_candidates` | unit | Domain allowlist admits real social URLs, rejects news/stock/aggregator hosts, de-duplicates |
| `test_registry` | integration, `eth-tester` | Deploy, anchor, read back; `count()` increments; empty hash and empty URL revert |
| `test_verify_tamper` | integration, `eth-tester` | Round-trip verify passes; a one-byte mutation produces `EvidenceIntegrityError` |
| `test_pipeline_no_match` | integration, mocked search | Zero verified candidates raises `NoVerifiedMatchError` rather than anchoring anything |
| `test_search_error` | unit, mocked httpx | A provider 500 raises `SearchProviderError` and is not reported as an empty result |

`test_evidence` and `test_verify_tamper` are the two that protect the actual claim being made to
the judges. They are written first.

---

## 12. Build phasing

Today is 2026-08-31. Deadline is 2026-09-07, 23:59.

| Day | Date | Goal | Exit gate |
|---|---|---|---|
| 1 | Aug 31 | **Spike only (~45 min).** `uv venv`; verify insightface + onnxruntime wheels install clean on arm64; one throwaway script: crop a face, upload to imgbb, hit SerpAPI Lens, print raw results | **Does Lens return actual social-media post URLs for the chosen public figure, or only news/stock/aggregator pages?** |
| 2 | Sep 1 | Thin end-to-end slice on `eth-tester` with a stubbed candidate; `test_evidence` and `test_verify_tamper` written first | `run` completes; `verify` passes; tamper fails |
| 3 | Sep 2 | Real search leg: uploader, lens, candidates. Stub deleted | A real social post URL reaches the pipeline |
| 4 | Sep 3 | Step-4 face verification, ranking, threshold sanity-check per §5.4 | Real cosine score on a real candidate |
| 5 | Sep 4 | Base Sepolia deploy; README; tests to 80% | Live Basescan transaction link |
| 6 | Sep 5 | Record end to end; include the secondary self-face pass showing the low-confidence path | Video uploaded and link verified working |
| 7 | Sep 6–7 | Buffer, final repo review, submit | Submitted |

Day 1 is a genuine gate, not a formality. Everything except the search leg is deterministic local
work that will certainly come together; the search leg is the only part not under our control, so
its feasibility must be established on day one rather than discovered on day five.

Two days of buffer are deliberate. The task allows no resubmissions.

---

## 13. Demo subjects

- **Primary: a public figure** with a large, well-indexed public web presence. This is what makes
  the search leg return real social URLs, and therefore what makes the recording work. The choice
  is disclosed in the README alongside the limitations.
- **Secondary: the author's own face**, run on camera as a second pass. This is expected to
  produce either no match or a low-confidence result, and it is shown deliberately — it
  demonstrates the negative path, proves the threshold is doing real work, and is honest about
  the system's actual reach.

---

## 14. Risks and mitigations

| # | Risk | Mitigation |
|---|---|---|
| R1 | Google Lens accepts a URL, not raw bytes — the face crop must be hosted before it can be searched. This is the moving part most likely to be underestimated. | `search.uploader` exists solely for this and is validated on Day 1, before anything is built on top of it |
| R2 | Lens may return zero social URLs for a bare face crop; crops are low-context and Lens sometimes prefers whole scenes | Query both the crop and the full photo and union the candidates. Step-4 face verification remains the arbiter, so the embedding stays load-bearing either way. If results are still thin, add a TinEye fallback on Day 4 |
| R3 | Social platforms may block hotlinked image fetches (403 on Instagram), breaking step-4 re-embedding | Browser User-Agent and Referer headers first; a Playwright fallback for image retrieval only if needed. `CandidateFetchError` skips the candidate rather than failing the run |
| R4 | Testnet RPC flakiness or faucet exhaustion on recording day | The `local` eth-tester path is kept working throughout and recorded as a fallback. The task explicitly permits a local or simulated chain |
| R5 | R2 states results must not be hardcoded, and there are no resubmissions | The Day 2 stub is deleted on Day 3 and its removal is verified in the final repo review. No fixture in the shipped code contains a pre-picked result |
| R6 | Model download (~300MB for `buffalo_l`) on first run could stall a live demo | Models are pre-warmed before recording; `models/` is git-ignored and the README documents the first-run download |

---

## 15. Ethics and limitations

This section is a README requirement and is also the part most submissions get wrong. It states,
plainly:

- The demo runs against a public figure with a large existing public web footprint. The tool is
  not pointed at private individuals, and the README says so.
- Face recognition accuracy degrades sharply across pose, illumination, age gap, occlusion, and —
  well documented in the literature — across demographic groups. A single cosine score carries no
  guarantee of fairness across subjects.
- A cosine similarity above threshold is **evidence of a probable match, not an identification**.
  The system produces a ranked hypothesis, not a fact.
- The blockchain proves **when a claim was recorded and that it has not been altered since**. It
  does not, and cannot, prove the claim is true. Anchoring a wrong match produces a permanent,
  tamper-evident record of a wrong match. This distinction is the single most important
  limitation of the entire project and is stated in the README in these terms.
- Reverse image search reaches only publicly indexed content. Absence of a match is not evidence
  of absence of a social media presence.

---

## 16. Future work

Listed in the README, not built:

- Pin the evidence bundle to IPFS and anchor the CID alongside the hash, so the evidence itself is
  content-addressed rather than only its digest.
- A second search lane that crawls open social protocols (Bluesky AT Protocol, Mastodon) at
  runtime and performs vector similarity search over freshly computed face embeddings. Cut here
  as circular for a demo, but the correct architecture for a system that must not depend on a
  commercial search intermediary.
- Merkle-ise the bundle to allow selective disclosure of individual evidence fields.
- Multi-face probes: anchor a record per detected identity rather than the highest-scoring face.
