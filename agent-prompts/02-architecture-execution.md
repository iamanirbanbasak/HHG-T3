# 02 — Architecture Execution Plan

**Status:** Frozen. This file owns the component boundaries, interface signatures, and the
exception hierarchy. Milestones **quote** this file; they do not re-derive interfaces.

If a milestone needs an interface this file does not define, that means this file is incomplete.
Fix it here, then cite it. Do not invent a local interface inside a milestone.

---

## 1. Component boundaries (frozen names)

These twelve names are used verbatim everywhere — module paths, test names, milestone headings:

```text
face.detect
face.embed
face.similarity

search.uploader
search.lens
search.candidates

pipeline

evidence

chain.compile
chain.deploy
chain.registry

cli
```

Plus two cross-cutting modules that are not pipeline stages:

```text
config      # typed configuration, constructed once at the CLI boundary
errors      # the exception hierarchy below
```

## 2. Dependency direction

Dependencies point downward only. An upward import is an architecture violation and fails the
M16 import-graph audit (NFR-013).

```text
                          cli
                           │
            ┌──────────────┼──────────────┐
            │              │              │
        pipeline       chain.deploy   chain.registry
            │              │              │
   ┌────────┼────────┐     └──────┬───────┘
   │        │        │            │
 face.*  search.*  evidence   chain.compile
   │        │        │            │
   └────────┴────────┴────────────┘
                  │
            config, errors
```

Rules:

- `config` and `errors` are leaves. They import nothing from the project.
- `face.*`, `search.*`, `evidence`, and `chain.*` never import `pipeline` or `cli`.
- `evidence` never imports `face.*` or `search.*`. It receives plain data.
- Only `cli` constructs `Config`. Everything else receives it. (FR-054)
- Only `config.py` reads `os.environ`. (FR-054)

## 3. Interfaces

Signatures are normative. Milestones implement these exactly.

### 3.1 `face.detect`

```python
@dataclass(frozen=True)
class DetectedFace:
    bbox: tuple[int, int, int, int]        # x, y, w, h
    landmarks: np.ndarray                  # (5, 2) float32
    det_score: float
    aligned: np.ndarray                    # (112, 112, 3) uint8

def detect_faces(image: np.ndarray) -> list[DetectedFace]: ...
def load_image(path: Path) -> np.ndarray: ...
```

Highest `det_score` is the probe (FR-003). Zero detections raises `NoFaceDetectedError` (FR-005).

### 3.2 `face.embed`

```python
def embed(aligned: np.ndarray) -> np.ndarray:       # (512,) float32, L2-normalised
```

### 3.3 `face.similarity`

```python
def cosine(a: np.ndarray, b: np.ndarray) -> float:  # [-1.0, 1.0]
```

Pure function. Imports numpy only. No I/O, no config.

### 3.4 `search.uploader`

```python
def upload(path: Path, cfg: Config) -> str:         # public HTTPS URL
```

Raises `SearchProviderError` on non-2xx. Sets a one-day expiry (FR-011).

### 3.5 `search.lens`

```python
@dataclass(frozen=True)
class Candidate:
    page_url: str
    image_url: str
    title: str
    source: str

def search(image_url: str, cfg: Config) -> list[Candidate]: ...
```

**A provider error raises `SearchProviderError`. It never returns `[]`.** An empty result set is
a legitimate `[]`. These two outcomes are distinct and must stay distinct (FR-052, HC-17).

### 3.6 `search.candidates`

```python
def filter_social(cands: list[Candidate], cfg: Config) -> list[Candidate]: ...
def normalise_url(url: str) -> str: ...
```

Order-stable. De-duplicates on `normalise_url(page_url)` (FR-016).

### 3.7 `pipeline`

```python
@dataclass(frozen=True)
class ScoredCandidate:
    candidate: Candidate
    cosine: float
    image_path: Path

def run(image: Path, cfg: Config) -> EvidenceBundle: ...
```

Owns the load-bearing loop (HC-03, HC-06): for each filtered candidate, fetch the image, detect,
align, embed, score against the probe, reject below `tau`. Raises `NoVerifiedMatchError` when
nothing survives (FR-022).

### 3.8 `evidence`

```python
def canonicalise(bundle: dict) -> bytes: ...
def evidence_hash(bundle: dict) -> bytes: ...        # 32 bytes, keccak256
def sha256_file(path: Path) -> str: ...              # lowercase hex
def build_bundle(...) -> dict: ...
def rebuild_from_artifacts(run_dir: Path) -> dict: ...
def similarity_bps(cosine: float) -> int: ...
```

Canonical form is exactly:

```python
json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
```

`rebuild_from_artifacts` recomputes every digest from the stored **source files**. It must never
read a digest out of a stored bundle and reuse it (FR-039, HC-14).

### 3.9 `chain.compile` / `chain.deploy` / `chain.registry`

```python
def compile_registry() -> tuple[list[dict], str]:            # (abi, bytecode)
def deploy(w3: Web3, acct) -> str:                           # contract address

class Registry:
    def __init__(self, w3: Web3, address: str, abi: list[dict]) -> None: ...
    def anchor(self, evidence_hash: bytes, post_url: str, sim_bps: int) -> tuple[int, str]: ...
    def get(self, record_id: int) -> Record: ...
    def count(self) -> int: ...
```

`Registry` is provider-agnostic. The same object works against `eth-tester` and Base Sepolia;
only the injected `Web3` differs (FR-036).

### 3.10 `config`

```python
@dataclass(frozen=True)
class Config:
    network: Literal["local", "base-sepolia"]
    rpc_url: str | None
    private_key: str | None            # never logged
    contract_address: str | None
    serpapi_key: str | None            # never logged
    imgbb_key: str | None              # never logged
    threshold: float = 0.45
    social_domains: tuple[str, ...] = DEFAULT_SOCIAL_DOMAINS
    max_candidates: int = 20
    fetch_timeout_s: float = 10.0
    max_image_bytes: int = 8 * 1024 * 1024
    fetch_concurrency: int = 4

def load_config(**overrides) -> Config: ...   # the ONLY os.environ reader in the project
```

## 4. Error hierarchy (frozen, verbatim from spec §10)

```text
FaceChainError                  # base
|- NoFaceDetectedError          # step 1: probe image has no detectable face
|- SearchProviderError          # steps 3: SerpAPI or imgbb returned an error
|- CandidateFetchError          # step 4: candidate image could not be retrieved
|- NoVerifiedMatchError         # step 4: zero candidates cleared tau
|- ChainError                   # steps 6-7: RPC, revert, or receipt failure
\- EvidenceIntegrityError       # step 7: recomputed hash != on-chain hash
```

Behavioural rules, normative:

- `SearchProviderError` is never converted into an empty result (FR-052).
- `CandidateFetchError` on one candidate is logged and skipped; the run continues (FR-053).
- `EvidenceIntegrityError` is the **success** condition of `verify --tamper` and the **failure**
  condition of plain `verify`. The CLI maps them to different exit codes (FR-043, FR-047).

## 5. Critical path

```text
Input
→ Detection
→ Alignment
→ Embedding
→ Upload
→ Lens
→ Candidate filtering
→ Candidate image fetch
→ Candidate detection
→ Candidate embedding
→ Similarity
→ Ranking
→ Evidence bundle
→ Hash
→ Blockchain anchor
→ Re-verification
```

Performance-critical segments (NFR-001..003), in expected cost order: model load (once),
candidate fetch (network-bound, parallelisable under a cap), candidate embedding (CPU-bound),
Lens round-trips (network-bound, exactly two), anchor transaction (chain-bound).

Never optimise by removing verification, reducing candidate count below what the threshold needs,
or introducing unbounded concurrency.

## 6. Data flow

```text
image path ──> load_image ──> detect_faces ──> probe DetectedFace
                                                  │
                          ┌───────────────────────┼──────────────────┐
                          │                                          │
                    aligned crop                              probe embedding
                          │                                          │
                    upload() ──> crop URL                            │
                          │                                          │
                    lens.search(crop URL) ──┐                        │
                    lens.search(photo URL) ─┴─> union ──> filter ──> │
                                                            │        │
                                                   per candidate:    │
                                            fetch ─> detect ─> embed │
                                                            │        │
                                                            └─ cosine ┘
                                                                  │
                                                    threshold ──> rank ──> top
                                                                  │
                          artifacts/<run-id>/ <── persist ────────┘
                                    │
                          rebuild_from_artifacts
                                    │
                          canonicalise ──> keccak256 ──> anchor()
```

## 7. Error flow

```text
load_image        ──> NoFaceDetectedError (via detect)
detect_faces      ──> NoFaceDetectedError            ──> CLI exit 2
uploader.upload   ──> SearchProviderError            ──> CLI exit 3
lens.search       ──> SearchProviderError            ──> CLI exit 3
candidate fetch   ──> CandidateFetchError            ──> logged, candidate skipped, run continues
pipeline.run      ──> NoVerifiedMatchError           ──> CLI exit 4  (a legitimate outcome)
chain.*           ──> ChainError                     ──> CLI exit 5
verify            ──> EvidenceIntegrityError         ──> CLI exit 1
verify --tamper   ──> EvidenceIntegrityError         ──> CLI exit 0  (expected)
```

## 8. Configuration flow

`cli` calls `load_config()` once, applies flag overrides, and passes the frozen `Config` down.
No other module reads the environment. Tests construct `Config` directly and never touch
`os.environ` (FR-054, NFR-009).

## 9. Artifact flow

```text
artifacts/<run-id>/
├── probe.jpg              # the input image, copied verbatim
├── probe_aligned.png      # 112x112 crop
├── candidate.jpg          # the winning candidate's image
├── post_text.txt          # the winning candidate's post text  (tamper target, FR-045)
├── evidence.json          # the canonical bundle
└── receipt.json           # record id, tx hash, network, block, contract address
```

`verify` reads only this directory plus the RPC endpoint. Nothing else (FR-040, NFR-015).

## 10. Blockchain flow

```text
compile_registry()  ──> (abi, bytecode)        # py-solc-x, solc 0.8.24 pinned
deploy(w3, acct)    ──> address                # written to receipt.json / .env
Registry.anchor()   ──> (record_id, tx_hash)   # append-only
Registry.get(id)    ──> Record                 # eth_call, the only external read in verify
```

## 11. Test boundaries

| Layer | Test type | External deps |
|---|---|---|
| `face.*`, `evidence`, `search.candidates` | unit | none |
| `search.uploader`, `search.lens` | unit | mocked httpx |
| `chain.*` | integration | `eth-tester` only |
| `pipeline` | integration | mocked providers, real face models |
| `cli` verify/tamper | integration | `eth-tester`, local artifacts |
| full run | e2e, marked | real SerpAPI, real imgbb, real testnet |

Only e2e tests touch real external services, and they are explicitly marked so ordinary runs skip
them (NFR-009).
