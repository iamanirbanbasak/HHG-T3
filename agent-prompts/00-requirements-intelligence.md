# 00 — Requirements Intelligence

**Source of truth:** `docs/superpowers/specs/2026-08-31-face-chain-design.md`
**Status:** Frozen. This file owns the `FR-###` / `NFR-###` ID namespace.

Every other document in `agent-prompts/` cites these IDs. No document restates a requirement in
its own words. If a requirement is missing here, add it here first, then cite it.

---

## 2.1 Functional requirements

Legend for **Validation**: `unit` / `integration` / `e2e` / `audit` (static repo inspection).

### Face pipeline — detection

| ID | Requirement | Source | Required behaviour | Implementation | Validation | Depends on | Risk |
|---|---|---|---|---|---|---|---|
| FR-001 | Load and decode an input image | §3 | Accept JPEG/PNG from a filesystem path; reject unreadable/malformed input with a typed error | `face/detect.py` | unit | — | Low |
| FR-002 | Detect faces with SCRFD | §4.1 | Return zero or more detections, each with `bbox`, `landmarks`, `det_score` | `face/detect.py` | unit | FR-001 | Low |
| FR-003 | Select the highest-scoring detection as the probe | §4.1 | Deterministic selection by `det_score` descending | `face/detect.py` | unit | FR-002 | Low |
| FR-004 | Record that multiple faces existed | §4.1, §5.1 | `probe.faces_detected` in the bundle records the count | `face/detect.py`, `evidence.py` | unit | FR-002 | Low |
| FR-005 | Raise `NoFaceDetectedError` when zero faces are found | §4.1, §10 | Never fabricate a detection or an embedding | `face/detect.py` | unit | FR-002 | Low |
| FR-006 | Align to a 112x112 crop using landmarks | §4.1 | Standard ArcFace 5-point similarity transform | `face/detect.py` | unit | FR-003 | Med |

### Face pipeline — embedding

| ID | Requirement | Source | Required behaviour | Implementation | Validation | Depends on | Risk |
|---|---|---|---|---|---|---|---|
| FR-007 | Produce a 512-d ArcFace embedding | §4.2 | `embed(aligned) -> np.ndarray` shape `(512,)`, float32 | `face/embed.py` | unit | FR-006 | Low |
| FR-008 | L2-normalise the embedding | §4.2, master §11 | `norm(v) == 1.0` within float tolerance | `face/embed.py` | unit | FR-007 | Low |
| FR-009 | Provide cosine similarity | §4.3 | Pure function, range `[-1.0, 1.0]`, symmetric | `face/similarity.py` | unit | FR-008 | Low |

### Search — query generation

| ID | Requirement | Source | Required behaviour | Implementation | Validation | Depends on | Risk |
|---|---|---|---|---|---|---|---|
| FR-010 | Publish the query image at a public HTTPS URL | §4.4 | Google Lens accepts a URL, not raw bytes | `search/uploader.py` | integration (mocked) + e2e | FR-006 | **High** |
| FR-011 | Uploads expire after one day | §4.4 | imgbb expiry parameter set | `search/uploader.py` | unit | FR-010 | Low |
| FR-012 | Reverse-image-search the **aligned face crop** | §2, §4.7, master §12 | The crop is the primary visual query. The embedding vector itself is never sent to the provider | `pipeline.py` | integration (mocked) + e2e | FR-010 | **High** |
| FR-013 | Also search the full photo | §4.7 | Recall widening only; never bypasses face verification | `pipeline.py` | integration (mocked) | FR-010 | Med |
| FR-014 | Union the two candidate sets | §4.7 | Order-stable union before filtering | `pipeline.py` | unit | FR-012, FR-013 | Low |

### Search — candidate handling

| ID | Requirement | Source | Required behaviour | Implementation | Validation | Depends on | Risk |
|---|---|---|---|---|---|---|---|
| FR-015 | Filter candidates to a social-domain allowlist | §4.6 | Configurable allowlist; Mastodon `/@handle/` heuristic | `search/candidates.py` | unit | FR-014 | Med |
| FR-016 | De-duplicate by normalised `page_url` | §4.6 | Provider ordering preserved | `search/candidates.py` | unit | FR-015 | Low |
| FR-017 | Fetch each candidate's image | §4.7, §14 R3 | Browser UA/Referer headers; bounded size and timeout | `pipeline.py` | integration (mocked) | FR-016 | **High** |
| FR-018 | Independently detect and embed each candidate face | §2, §4.7 | This is what makes the embedding load-bearing | `pipeline.py` | integration | FR-017, FR-007 | **High** |
| FR-019 | Score each candidate by cosine against the probe | §2, §4.7 | Numeric score retained for ranking and evidence | `pipeline.py` | unit | FR-018, FR-009 | Low |
| FR-020 | Reject candidates below `tau` | §5.4 | Default `tau = 0.45`, configurable via `--threshold` | `pipeline.py` | unit | FR-019 | Med |
| FR-021 | Select the highest-scoring surviving candidate | §5.1 | Exactly one match is anchored per run | `pipeline.py` | unit | FR-020 | Low |
| FR-022 | Raise `NoVerifiedMatchError` when none clear `tau` | §4.7, §10 | Never fabricate or downgrade a match to force a result | `pipeline.py` | unit | FR-020 | Low |

### Evidence

| ID | Requirement | Source | Required behaviour | Implementation | Validation | Depends on | Risk |
|---|---|---|---|---|---|---|---|
| FR-023 | Persist raw artifacts under `artifacts/<run-id>/` | §5.1 | Probe image, aligned crop, candidate image, post text | `evidence.py` | integration | FR-021 | Low |
| FR-024 | Compute SHA-256 digests of artifacts | §5.2 | Lowercase hex, no prefix | `evidence.py` | unit | FR-023 | Low |
| FR-025 | Assemble the `hhg-t3/evidence/v1` bundle | §5.1 | Exact schema from spec §5.1 | `evidence.py` | unit | FR-024 | Low |
| FR-026 | Canonicalise deterministically | §4.8, master §14 | `json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")` | `evidence.py` | unit (golden) | FR-025 | **High** |
| FR-027 | Hash the canonical bundle with keccak256 | §5.2 | Solidity-native `bytes32`. Never merged with SHA-256 | `evidence.py` | unit (golden) | FR-026 | Med |
| FR-028 | Encode similarity as basis points | §5.3 | `max(0, min(10000, round(cosine * 10000)))`, `uint16` | `evidence.py` | unit | FR-019 | Low |

### Blockchain

| ID | Requirement | Source | Required behaviour | Implementation | Validation | Depends on | Risk |
|---|---|---|---|---|---|---|---|
| FR-029 | Compile the contract with `py-solc-x` | §8 | Pinned solc 0.8.24. No Foundry, no Hardhat, no Node | `chain/compile.py` | integration | — | Med |
| FR-030 | Deploy to the selected network | §6 | Same code path for `local` and `base-sepolia` | `chain/deploy.py` | integration | FR-029 | Med |
| FR-031 | `anchor(evidenceHash, postUrl, similarityBps)` | §6 | Append-only; emits `MatchAnchored`; returns record id | `contracts/`, `chain/registry.py` | integration | FR-030 | Low |
| FR-032 | `get(id)` returns the full record | §6 | Used by re-verification | `chain/registry.py` | integration | FR-031 | Low |
| FR-033 | `count()` returns the record total | §6 | Increments on each anchor | `chain/registry.py` | integration | FR-031 | Low |
| FR-034 | `verify(id, candidate)` on-chain | §6 | Present for completeness; CLI uses `get()` so the comparison is visible | `contracts/` | integration | FR-031 | Low |
| FR-035 | Revert on empty hash or empty URL | §6 | `require` guards | `contracts/` | integration | FR-031 | Low |
| FR-036 | Select the network at the configuration boundary | §6, §9, master §15 | No module reads network state directly | `config.py` | audit | — | Med |
| FR-037 | No update or delete path exists on-chain | §6 | Mutability would defeat the purpose | `contracts/` | audit | FR-031 | Low |

### Re-verification

| ID | Requirement | Source | Required behaviour | Implementation | Validation | Depends on | Risk |
|---|---|---|---|---|---|---|---|
| FR-038 | Read `evidenceHash` from the chain via `eth_call` | §7 | A real network read; the only permitted external read | `cli.py`, `chain/registry.py` | integration | FR-032 | Low |
| FR-039 | Rebuild the bundle from local artifacts | §7 | Recompute `probe.image_sha256`, `match.image_sha256`, `match.post_text_sha256` from stored source files | `evidence.py` | integration | FR-023 | **High** |
| FR-040 | Never re-fetch a hosted URL during verification | §7 | Not the expired imgbb crop, not the platform image | `cli.py` | audit + integration | FR-039 | **High** |
| FR-041 | Display both hashes side by side | §7 | On-chain and recomputed, both visible | `cli.py` | e2e | FR-038, FR-039 | Low |
| FR-042 | Display network and block number | §7 | Demo legibility | `cli.py` | e2e | FR-038 | Low |
| FR-043 | Report MATCH or MISMATCH explicitly | §7 | Exit code 0 / 1 respectively for plain `verify` | `cli.py` | integration | FR-041 | Low |

### Tamper demonstration

| ID | Requirement | Source | Required behaviour | Implementation | Validation | Depends on | Risk |
|---|---|---|---|---|---|---|---|
| FR-044 | `verify --tamper` copies artifacts to a scratch location | §7, master §17 | The original run directory must survive intact | `cli.py` | integration | FR-039 | Med |
| FR-045 | Mutate one byte of the **post-text source file** | §7, master §17 | Mutation at source-evidence level, never editing a stored digest | `cli.py` | integration | FR-044 | **High** |
| FR-046 | The altered digest propagates to a different bundle hash | §7 | `match.post_text_sha256` changes, therefore the bundle hash changes | `evidence.py` | integration | FR-045 | Low |
| FR-047 | Produce a MISMATCH against the unchanged on-chain hash | §7 | `EvidenceIntegrityError` is the success condition here | `cli.py` | integration | FR-046 | Low |
| FR-048 | Leave the original artifacts byte-identical | master §17 | Assert digests before and after | `cli.py` | integration | FR-044 | Med |

### CLI and reporting

| ID | Requirement | Source | Required behaviour | Implementation | Validation | Depends on | Risk |
|---|---|---|---|---|---|---|---|
| FR-049 | Provide `scan`, `search`, `anchor`, `verify`, `run`, `deploy` | §4.10, master §22 | Each step individually invocable so one leg can be re-recorded | `cli.py` | integration | — | Low |
| FR-050 | Show stage, candidate count, score, threshold, match, hash, network, tx, result | master §22 | Rich output legible in a screen recording | `cli.py` | e2e | FR-049 | Low |
| FR-051 | Never label cosine similarity as a confidence percentage | §5.3, §15, master §19 | `similarityBps` is a raw cosine encoding. 10000 means cosine 1.0, not "100% certain" | `cli.py`, README | audit | — | Med |

### Cross-cutting correctness

| ID | Requirement | Source | Required behaviour | Implementation | Validation | Depends on | Risk |
|---|---|---|---|---|---|---|---|
| FR-052 | A provider error must never collapse into "no results" | §10, master §20 | `SearchProviderError` and an empty candidate list are distinct outcomes, reported differently | `search/lens.py`, `cli.py` | unit | — | **High** |
| FR-053 | A single candidate fetch failure skips that candidate only | §10 | `CandidateFetchError` is logged; the run continues with the remainder | `pipeline.py` | unit | FR-017 | Med |
| FR-054 | `Config` is constructed once and passed down | §9, master §30 | No module reads `os.environ` directly | `config.py` | audit | — | Med |
| FR-055 | No hardcoded or pre-selected search result ships | master §13 | No fixture masquerading as live search output in the production path | all | audit | — | **High** |
| FR-056 | README covers purpose, run instructions, chain, limitations | Task C2, §15 | Including the probable-match-not-identity claim | `README.md` | audit | — | Med |

---

## 2.2 Non-functional requirements

| ID | Category | Requirement | Target | Validation |
|---|---|---|---|---|
| NFR-001 | Latency | The critical path is measured, not guessed | p50/p95 recorded per stage in `10-deadline-plan.md` reporting | `06-performance-engineering.md` harness |
| NFR-002 | Latency | Model load happens once per process | Warm-up before timed stages; no reload per candidate | perf test |
| NFR-003 | Latency | Candidate fetches use bounded concurrency | Explicit cap, never unbounded | audit + perf test |
| NFR-004 | Accuracy | `tau` is a validated operating point, not an assumed constant | Separation between same- and different-identity distributions is measured and recorded | `07-accuracy-engineering.md` |
| NFR-005 | Accuracy | Cosine is never presented as probability | No "%" adjacent to a similarity value anywhere | audit |
| NFR-006 | Reliability | Every failure mode in `08-reliability-engineering.md` has a test | Full list covered | reliability suite |
| NFR-007 | Determinism | Canonical serialisation is byte-stable across runs and key orderings | Golden test does not drift | unit (golden) |
| NFR-008 | Determinism | The same bundle always produces the same hash | Cross-process stability | unit |
| NFR-009 | Testability | Unit tests require no external service | All providers mocked | CI run with no network |
| NFR-010 | Testability | Chain integration tests use `eth-tester` | No testnet dependency in ordinary test runs | test suite |
| NFR-011 | Security | Secrets never committed and never logged | `.env` ignored; no key in any log line | `09-security-hardening.md` |
| NFR-012 | Security | Downloaded content is size- and time-bounded | Explicit caps on candidate image fetches | audit + test |
| NFR-013 | Maintainability | Components stay within the frozen boundaries of `02` | No cross-layer reach-through | audit |
| NFR-014 | CLI usability | Every stage is independently runnable | Six commands, each usable alone | integration |
| NFR-015 | Offline verification | `verify` works with no access to any social platform or image host | Only the RPC endpoint is reachable | integration (network-isolated) |
| NFR-016 | Reproducibility | A fresh clone can reach a passing test suite from the README alone | Clean-machine install path documented and exercised | `M18` |
| NFR-017 | Coverage | 80% minimum, per project standards | `pytest --cov` | CI |

---

## 2.3 Hard constraints

These must not be violated. Violation of any one is a milestone `FAILED`, not a warning.

| # | Constraint | Enforced by |
|---|---|---|
| HC-01 | Face detection actually occurs | FR-002, FR-005 |
| HC-02 | Face embedding is actually generated | FR-007, FR-008 |
| HC-03 | The embedding materially participates in candidate verification | FR-018, FR-019, FR-020 |
| HC-04 | The search result is not hardcoded or pre-selected | FR-055 |
| HC-05 | A genuine reverse-image-search operation is performed | FR-012 |
| HC-06 | Candidates are independently face-verified | FR-018 |
| HC-07 | Similarity is calculated numerically | FR-019 |
| HC-08 | Candidates below `tau` are rejected | FR-020 |
| HC-09 | The highest-scoring valid candidate is selected | FR-021 |
| HC-10 | Evidence is canonicalised deterministically | FR-026 |
| HC-11 | The bundle is hashed | FR-027 |
| HC-12 | The hash is anchored on-chain | FR-031 |
| HC-13 | Re-verification retrieves the hash from the blockchain | FR-038 |
| HC-14 | Re-verification independently reconstructs evidence from local artifacts | FR-039 |
| HC-15 | The tamper demo modifies source evidence, not a digest | FR-045 |
| HC-16 | Verification works without the original hosted image URLs | FR-040 |
| HC-17 | Provider errors are never silently read as "no results" | FR-052 |
| HC-18 | The implementation stays CLI-only | Non-goal NG-01 |
| HC-19 | Results are described as probable-match evidence, not identity proof | FR-051, FR-056 |

## 2.4 Non-goals

Do not build these. Building them is scope creep and costs deadline days.

| # | Non-goal | Source |
|---|---|---|
| NG-01 | Any web frontend, hosted service, or HTTP API | Task C1, §1 |
| NG-02 | Authentication or multi-user support | §1 |
| NG-03 | Merkle-ised bundles / selective disclosure | §8 rejected alternatives |
| NG-04 | IPFS pinning | §8 rejected alternatives |
| NG-05 | A locally crawled Bluesky/Mastodon face index | §8 rejected alternatives |
| NG-06 | Scraping PimEyes, Yandex, or Google directly | §8 rejected alternatives |
| NG-07 | Authenticated scraping of private social surfaces | §1 |
| NG-08 | Anchoring every verified candidate rather than the top one | §5.1 |
| NG-09 | Production identity claims of any kind | §15 |

---

## 2.5 Risks

| ID | Risk | Prob | Impact | Mitigation | Detection | Fallback | Validated at |
|---|---|---|---|---|---|---|---|
| RK-01 | Google Lens returns no social-media URLs for a bare face crop | **High** | **Critical** — R2 unsatisfiable | Query crop *and* full photo, union; face verification arbitrates | M00 spike prints raw candidate domains | Add TinEye or a second provider; widen allowlist | **M00** |
| RK-02 | The crop-hosting hop (imgbb) fails or needs an account that does not exist | Med | **Critical** — blocks all search | Validate the uploader end to end before anything is built on it | M00 spike uploads and retrieves | Alternative host (catbox/0x0); provider that accepts raw bytes | **M00** |
| RK-03 | Social platforms 403 hotlinked candidate images | **High** | High — breaks FR-018 | Browser UA/Referer; per-candidate skip, not run failure | `CandidateFetchError` rate in run output | Playwright fallback for image retrieval only | M08 |
| RK-04 | InsightFace / onnxruntime wheels fail on arm64 | Low | **Critical** | Verify install before writing pipeline code | M00 spike imports and runs a detection | CPU-only ONNX build; DeepFace as last resort (**material deviation — ask**) | **M00** |
| RK-05 | Testnet RPC flakiness or faucet exhaustion on recording day | Med | High | Keep the `local` eth-tester path working throughout | `deploy`/`anchor` failures | Record against `local`; the task permits a simulated chain | M06, M17 |
| RK-06 | A dev stub survives into the shipped repo | Med | **Critical** — HC-04 violation, no resubmissions | Stub deleted at M07; audited at M18 | `99-final-audit.md` grep sweep | Delete and re-verify | M18 |
| RK-07 | Canonical JSON drifts and verification fails spuriously | Med | High | Golden test written before the pipeline exists | Golden hash mismatch | Pin serialisation; never "fix" by loosening the comparison | M04 |
| RK-08 | The verifier accidentally self-compares | Med | **Critical** — HC-13/14 hollow | On-chain read and local recompute are separate code paths | Audit + a test that fails if the chain read is removed | Rewrite verify | M10, M18 |
| RK-09 | Model download (~300MB) stalls a live demo | Med | Med | Pre-warm before recording; document first-run download | Cold-start timing | Pre-downloaded model cache | M17 |
| RK-10 | 18 milestones do not fit the remaining days | **High** | Med | Must-ship vs if-time split in `10-deadline-plan.md` | Daily milestone burn-down | Drop M13; reduce M12 to measure-and-document | M18 |
| RK-11 | The negative-path (self-face) run unexpectedly produces a match | Low | Med | Report the score honestly rather than reframing the demo | M17 rehearsal | Show it as a real low-confidence result; do not suppress | M17 |

---

## 2.6 Ambiguities

**Unresolved. Do not resolve these silently.** Each materially affects the build; follow
`04-question-protocol.md` and ask.

| ID | Ambiguity | Why it matters | Blocks |
|---|---|---|---|
| AMB-01 | **Where does the labelled threshold-calibration set come from?** Master §19 requires same-identity and different-identity pairs. Spec §15 states the tool is not pointed at private individuals. The spec never says whose faces populate the evaluation set, and collecting labelled face pairs carries consent implications it does not resolve. | Determines whether `tau` is validated or assumed (NFR-004), and whether the calibration itself is ethically consistent with §15 | M12 |
| AMB-02 | **Base Sepolia wallet funding and key custody.** Who holds the private key, and is faucet ETH already obtained? | M06 cannot deploy publicly without it; RK-05 fallback depends on the answer | M06 |
| AMB-03 | **Does an imgbb account/API key exist?** The spec assumes the uploader works but never confirms provisioning. | RK-02. A day-one blocker hiding inside M07 if the answer is no | M00 |
| AMB-04 | **What does the demo show if the negative-path self-face run produces a match?** Spec §13 assumes it will not. | The recording plan (M17) branches on this; fabricating the expected outcome would violate HC-04 in spirit | M17 |
| AMB-05 | **Is the public figure chosen?** Spec §13 fixes the category, not the person. Lens recall varies enormously by subject. | M00 cannot run without a concrete subject | **M00** |
| AMB-06 | **`post_text` provenance.** The bundle hashes `match.post_text_sha256`, but the spec never states how post text is obtained when Lens returns only a page URL and a thumbnail. | FR-045's tamper target must exist. If post text cannot be retrieved, the tamper demo needs a different source artifact | M08 |
