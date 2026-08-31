# 01 — Requirements Traceability

**Status:** Frozen. This file decides which milestone owns which requirement.

Rules:

- Every `FR-###` and `NFR-###` from `00-requirements-intelligence.md` appears exactly once as an
  owning row. A requirement may be *exercised* by later milestones, but it is *owned* by one.
- Every row maps to an **executable** check. No row is satisfied by "agent should verify
  manually". Rows validated by `audit` are still executable: they are grep/AST sweeps run by
  `99-final-audit.md`, not human reading.
- A milestone may not be marked `PASS` while any requirement it owns lacks a passing test.

---

## Functional requirements

| ID | Requirement | Component | Milestone | Test | Acceptance criterion | Evidence |
|---|---|---|---|---|---|---|
| FR-001 | Load/decode input image | `face.detect` | M02 | `test_detect.py::test_loads_jpeg_and_png` | Both formats decode; malformed input raises typed error | pytest output |
| FR-002 | SCRFD detection | `face.detect` | M02 | `test_detect.py::test_detects_known_face` | Fixture image yields >=1 detection with `det_score > 0.5` | pytest output |
| FR-003 | Highest-scoring detection is the probe | `face.detect` | M02 | `test_detect.py::test_probe_is_highest_score` | Two-face fixture selects the higher score deterministically | pytest output |
| FR-004 | Record multi-face count | `face.detect`, `evidence` | M02 | `test_detect.py::test_records_face_count` | `faces_detected == 2` on two-face fixture | pytest output |
| FR-005 | `NoFaceDetectedError` on zero faces | `face.detect` | M02 | `test_detect.py::test_no_face_raises` | Blank image raises; no embedding produced | pytest output |
| FR-006 | 112x112 landmark alignment | `face.detect` | M02 | `test_detect.py::test_alignment_shape_and_stability` | Output is `(112,112,3)`; same input gives identical bytes | pytest output |
| FR-007 | 512-d ArcFace embedding | `face.embed` | M03 | `test_embed.py::test_embedding_shape_dtype` | shape `(512,)`, dtype float32 | pytest output |
| FR-008 | L2 normalisation | `face.embed` | M03 | `test_embed.py::test_embedding_is_l2_normalised` | `abs(norm - 1.0) < 1e-5` | pytest output |
| FR-009 | Cosine similarity | `face.similarity` | M03 | `test_similarity.py` | Identical vectors -> 1.0; orthogonal -> 0.0; symmetric; bounded | pytest output |
| FR-010 | Public URL for query image | `search.uploader` | M07 | `test_uploader.py::test_upload_returns_url` (mocked) + `M00` live check | Mocked path returns URL; live spike proves reachability | pytest + M00 report |
| FR-011 | Upload expires in one day | `search.uploader` | M07 | `test_uploader.py::test_sets_expiry` | Request payload carries the expiry parameter | pytest output |
| FR-012 | Lens searches the aligned crop | `pipeline` | M07 | `test_pipeline.py::test_crop_is_the_query` | Provider receives the crop URL; **no 512-float payload is ever sent** | pytest output |
| FR-013 | Lens also searches the full photo | `pipeline` | M07 | `test_pipeline.py::test_two_queries_issued` | Exactly two provider calls per run | pytest output |
| FR-014 | Union of candidate sets | `pipeline` | M08 | `test_pipeline.py::test_union_is_order_stable` | Union preserves first-seen order | pytest output |
| FR-015 | Social-domain allowlist | `search.candidates` | M08 | `test_candidates.py::test_allowlist` | Real social URLs admitted; news/stock/aggregator rejected | pytest output |
| FR-016 | De-duplicate by normalised URL | `search.candidates` | M08 | `test_candidates.py::test_dedupe` | Query-string and trailing-slash variants collapse to one | pytest output |
| FR-017 | Fetch candidate images | `pipeline` | M08 | `test_pipeline.py::test_fetch_bounded` | Size cap and timeout enforced; UA header present | pytest output |
| FR-018 | Independently detect+embed candidates | `pipeline` | M09 | `test_pipeline.py::test_candidate_independently_embedded` | **Removing the candidate-embedding call fails the test** | pytest output |
| FR-019 | Numeric cosine per candidate | `pipeline` | M09 | `test_pipeline.py::test_scores_are_numeric` | Every candidate carries a float score | pytest output |
| FR-020 | Reject below `tau` | `pipeline` | M09 | `test_pipeline.py::test_threshold_rejects` | Candidate at `tau - 0.01` is excluded | pytest output |
| FR-021 | Select the top scorer | `pipeline` | M09 | `test_pipeline.py::test_selects_highest` | Highest-scoring survivor is the anchored match | pytest output |
| FR-022 | `NoVerifiedMatchError` when none clear | `pipeline` | M09 | `test_pipeline_no_match.py` | Raises; nothing is anchored | pytest output |
| FR-023 | Persist run artifacts | `evidence` | M04 | `test_evidence.py::test_artifacts_written` | All four source artifacts exist on disk | pytest output |
| FR-024 | SHA-256 artifact digests | `evidence` | M04 | `test_evidence.py::test_sha256_digests` | Lowercase hex, matches `hashlib` reference | pytest output |
| FR-025 | Assemble `hhg-t3/evidence/v1` | `evidence` | M04 | `test_evidence.py::test_bundle_schema` | All spec §5.1 keys present, no extras | pytest output |
| FR-026 | Canonical serialisation | `evidence` | M04 | `test_evidence.py::test_canonical_json_stable` | Reordered-key input produces identical bytes | golden file |
| FR-027 | keccak256 bundle hash | `evidence` | M04 | `test_evidence.py::test_golden_hash` | Fixed bundle yields the committed golden hash | golden file |
| FR-028 | `similarityBps` encoding | `evidence` | M04 | `test_evidence.py::test_sim_bps_clamped` | `-0.3 -> 0`; `1.0 -> 10000`; rounding correct | pytest output |
| FR-029 | Compile with `py-solc-x` | `chain.compile` | M05 | `test_registry.py::test_compiles` | ABI and bytecode produced with solc 0.8.24 | pytest output |
| FR-030 | Deploy to selected network | `chain.deploy` | M05 | `test_registry.py::test_deploys_local` | Address returned on `eth-tester` | pytest output |
| FR-031 | `anchor()` | `chain.registry` | M05 | `test_registry.py::test_anchor_emits_event` | Returns id; `MatchAnchored` emitted | pytest output |
| FR-032 | `get()` | `chain.registry` | M05 | `test_registry.py::test_readback` | Round-trips every field | pytest output |
| FR-033 | `count()` | `chain.registry` | M05 | `test_registry.py::test_count_increments` | Increments per anchor | pytest output |
| FR-034 | On-chain `verify()` | `contracts` | M05 | `test_registry.py::test_onchain_verify` | True for stored hash, false otherwise | pytest output |
| FR-035 | Revert on empty hash/URL | `contracts` | M05 | `test_registry.py::test_rejects_empty` | Both revert with the stated reasons | pytest output |
| FR-036 | Network chosen at config boundary | `config` | M06 | `99-final-audit.md` grep sweep | No `os.environ` or RPC literal outside `config.py` | audit log |
| FR-037 | No update/delete on-chain | `contracts` | M05 | `test_registry.py::test_no_mutation_path` | ABI exposes no setter or delete | pytest output |
| FR-038 | Read hash from chain | `cli`, `chain.registry` | M10 | `test_verify.py::test_reads_from_chain` | **Test fails if the `eth_call` is stubbed out** | pytest output |
| FR-039 | Rebuild bundle from local artifacts | `evidence` | M10 | `test_verify.py::test_rebuild_from_disk` | Digests recomputed from source files, not read from the bundle | pytest output |
| FR-040 | Never re-fetch hosted URLs in verify | `cli` | M10 | `test_verify.py::test_offline_verify` | Passes with all outbound HTTP blocked except RPC | pytest output |
| FR-041 | Show both hashes | `cli` | M11 | `test_cli.py::test_verify_output` | Both values appear in stdout | captured stdout |
| FR-042 | Show network and block | `cli` | M11 | `test_cli.py::test_verify_output` | Network name and block number present | captured stdout |
| FR-043 | MATCH/MISMATCH + exit code | `cli` | M10 | `test_verify.py::test_exit_codes` | 0 on match, 1 on mismatch | exit status |
| FR-044 | `--tamper` copies artifacts | `cli` | M10 | `test_verify_tamper.py::test_uses_scratch_copy` | Mutation occurs outside the run directory | pytest output |
| FR-045 | Mutate post-text **source file** | `cli` | M10 | `test_verify_tamper.py::test_mutates_source_not_digest` | **Test asserts the bundle's digest field is never written directly** | pytest output |
| FR-046 | Digest change propagates | `evidence` | M10 | `test_verify_tamper.py::test_digest_propagates` | `post_text_sha256` differs, therefore bundle hash differs | pytest output |
| FR-047 | Tamper produces MISMATCH | `cli` | M10 | `test_verify_tamper.py::test_mismatch` | `EvidenceIntegrityError`; exit 0 for `--tamper` | pytest output |
| FR-048 | Originals untouched | `cli` | M10 | `test_verify_tamper.py::test_originals_intact` | Pre/post digests of the run directory are identical | pytest output |
| FR-049 | Six CLI commands | `cli` | M11 | `test_cli.py::test_all_commands_invocable` | Each returns 0 on `--help` and runs standalone | pytest output |
| FR-050 | Demo-legible Rich output | `cli` | M11 | `test_cli.py::test_output_fields_present` | All nine required fields rendered | captured stdout |
| FR-051 | Never label cosine a percentage | `cli`, README | M11 | `99-final-audit.md` grep sweep | No `%` adjacent to a similarity value | audit log |
| FR-052 | Provider error != empty result | `search.lens` | M07 | `test_search_error.py` | 500 raises `SearchProviderError`; empty body returns `[]` | pytest output |
| FR-053 | Candidate fetch failure skips one | `pipeline` | M08 | `test_pipeline.py::test_fetch_failure_skips` | Run completes with remaining candidates | pytest output |
| FR-054 | `Config` passed, not read ad hoc | `config` | M01 | `99-final-audit.md` grep sweep | `os.environ` appears only in `config.py` | audit log |
| FR-055 | No hardcoded result ships | all | M18 | `99-final-audit.md` sweep + `test_no_hardcoding.py` | No fixture URL reachable from the production path | audit log |
| FR-056 | README complete | `README.md` | M18 | `FINAL_VALIDATION.md` checklist | All four required topics present | checklist |

## Non-functional requirements

| ID | Requirement | Component | Milestone | Test | Acceptance criterion | Evidence |
|---|---|---|---|---|---|---|
| NFR-001 | Critical path measured | all | M13 | `bench/run_bench.py` | p50/p95 recorded per stage | bench report |
| NFR-002 | Model loaded once | `face.*` | M13 | `test_perf.py::test_single_model_load` | Loader invoked once per process | pytest output |
| NFR-003 | Bounded candidate concurrency | `pipeline` | M13 | `test_perf.py::test_concurrency_cap` | Concurrent fetches never exceed the cap | pytest output |
| NFR-004 | `tau` validated, not assumed | `pipeline` | M12 | `eval/threshold_report.md` | Same/different distributions and separation recorded | eval report |
| NFR-005 | Cosine never shown as probability | `cli` | M11 | audit sweep | No percentage formatting on similarity | audit log |
| NFR-006 | All failure modes tested | all | M14 | `tests/reliability/` | Every row of `08` has a test | pytest output |
| NFR-007 | Serialisation byte-stable | `evidence` | M04 | `test_evidence.py::test_canonical_json_stable` | Golden bytes unchanged | golden file |
| NFR-008 | Hash stable cross-process | `evidence` | M04 | `test_evidence.py::test_hash_stable_subprocess` | Same hash from a fresh interpreter | pytest output |
| NFR-009 | Unit tests need no network | all | M16 | full run with network disabled | Suite passes offline except marked e2e | CI log |
| NFR-010 | Chain tests use `eth-tester` | `chain.*` | M05 | `test_registry.py` | No RPC URL required | pytest output |
| NFR-011 | Secrets never committed or logged | all | M15 | `test_security.py::test_no_secret_in_logs` | No key material in captured output | pytest output |
| NFR-012 | Downloads size/time bounded | `pipeline` | M15 | `test_security.py::test_download_caps` | Oversized response aborted | pytest output |
| NFR-013 | Component boundaries respected | all | M16 | import-graph audit | No cross-layer reach-through | audit log |
| NFR-014 | Every stage runnable alone | `cli` | M11 | `test_cli.py::test_all_commands_invocable` | Six commands usable standalone | pytest output |
| NFR-015 | Verify works fully offline | `cli` | M10 | `test_verify.py::test_offline_verify` | Passes with only RPC reachable | pytest output |
| NFR-016 | Fresh clone reaches green tests | repo | M18 | clean-checkout run | README steps alone suffice | M18 report |
| NFR-017 | 80% coverage | all | M16 | `pytest --cov` | >= 80% | coverage report |

---

## Coverage check

| Bucket | Count | Owned by milestones |
|---|---|---|
| FR-001..FR-009 | 9 | M02, M03 |
| FR-010..FR-022 | 13 | M07, M08, M09 |
| FR-023..FR-028 | 6 | M04 |
| FR-029..FR-037 | 9 | M05, M06 |
| FR-038..FR-048 | 11 | M10 |
| FR-049..FR-056 | 8 | M01, M07, M08, M11, M18 |
| NFR-001..NFR-017 | 17 | M04, M05, M10..M16, M18 |
| **Total** | **73** | — |

Every ID above appears exactly once as an owning row. `99-final-audit.md` re-derives this count
from the file and fails if it drifts.
