# 05 — Testing Strategy

## Principle

The two tests that protect the actual claim made to judges are `test_evidence.py` and
`test_verify_tamper.py`. They are written **first**, before the pipeline they validate exists.
Everything else follows the normal TDD loop.

Target: 80% coverage minimum (NFR-017).

## Layering

| Layer | Depends on | Runs when |
|---|---|---|
| unit | nothing external | always, offline |
| integration (mocked providers) | `eth-tester`, real face models | always, offline |
| e2e (marked `@pytest.mark.e2e`) | real SerpAPI, imgbb, testnet | explicitly, never in the default run |

`pytest` default deselects `e2e`. `pytest -m e2e` runs them. A run with no network must be green
except for deselected e2e tests (NFR-009).

## Mock what is external, not what is internal

Mock: SerpAPI, imgbb, candidate image hosts, the RPC endpoint for unit tests.
Do not mock: `face.*`, `evidence`, `pipeline`, `chain.registry`. Those are the system under test.

Mocking an internal module to make a test pass is how the embedding becomes decorative without
anyone noticing.

## Required tests

Preserved verbatim from master §10. Each maps to an owning milestone in `01`.

| Test | Milestone | Guards |
|---|---|---|
| cosine similarity | M03 | FR-009 |
| canonical JSON | M04 | FR-026, NFR-007 |
| golden evidence hash | M04 | FR-027, NFR-008 |
| candidate domain filtering | M08 | FR-015 |
| candidate deduplication | M08 | FR-016 |
| contract deployment | M05 | FR-030 |
| contract anchoring | M05 | FR-031 |
| contract readback | M05 | FR-032 |
| empty hash rejection | M05 | FR-035 |
| empty URL rejection | M05 | FR-035 |
| successful re-verification | M10 | FR-038..FR-043 |
| tamper detection | M10 | FR-044..FR-048 |
| no verified match | M09 | FR-022 |
| provider failure | M07 | FR-052 |
| candidate fetch failure | M08 | FR-053 |

## Anti-cheat tests

These exist specifically to fail if the implementation becomes decorative. They are the tests a
reviewer would write to catch us.

| Test | Fails if |
|---|---|
| `test_candidate_independently_embedded` | the candidate-embedding call is removed and the pipeline still produces a match |
| `test_crop_is_the_query` | the embedding vector is sent to the provider, or the full photo replaces the crop as the primary query |
| `test_reads_from_chain` | the `eth_call` is stubbed and verification still passes |
| `test_mutates_source_not_digest` | `--tamper` writes to a digest field instead of a source file |
| `test_originals_intact` | `--tamper` mutates the real run directory |
| `test_offline_verify` | verification reaches for any URL other than the RPC endpoint |
| `test_no_hardcoding` | a fixture URL or pre-selected candidate is reachable from the production path |
| `test_search_error` | a provider 500 is reported as an empty result set |

Every one of these must fail when the corresponding shortcut is introduced. **Verify that**: at
M16, deliberately break each behaviour, confirm the test goes red, then revert. A test that
cannot fail is not a test.

## Golden files

`tests/fixtures/golden_bundle.json` and its expected keccak256 hash are committed. If the hash
changes, the change must be explained and deliberate. Never regenerate the golden file to match
new output as a way of making a red test green.

## Fixtures

Use factories over raw literals. Face fixtures are small, committed images. No fixture image may
be a real social-media post used as a stand-in for search output — that is RK-06 in embryo.
