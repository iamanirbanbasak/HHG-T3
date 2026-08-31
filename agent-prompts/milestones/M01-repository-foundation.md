# Milestone M01 — Repository Foundation

## Objective

Create the project skeleton, typed configuration, exception hierarchy, and a green test suite —
so every later milestone has somewhere to put code and something to run.

## Why This Milestone Exists

`Config` and `errors` are the two leaves of the dependency graph in `02` §2. Every other module
imports them. Building them first prevents each later milestone from inventing its own
configuration access and its own error types.

## Requirements Covered

Owns: FR-054, and the scaffolding for NFR-009, NFR-017.

## Preconditions

M00 gate is `PASS`, or the user has explicitly authorised proceeding on a `BLOCKED` gate.

## Inputs

`02-architecture-execution.md` §3.10 (Config) and §4 (error hierarchy).

## Expected Repository State Before Starting

`docs/`, `agent-prompts/`, `spike/`, `.gitignore`. No `src/`.

## Files To Create

```text
pyproject.toml
.env.example
src/facechain/__init__.py
src/facechain/config.py
src/facechain/errors.py
src/facechain/face/__init__.py
src/facechain/search/__init__.py
src/facechain/chain/__init__.py
tests/__init__.py
tests/conftest.py
tests/test_config.py
tests/test_errors.py
```

## Files To Modify

`.gitignore` — confirm `.env`, `artifacts/*`, `models/` are covered.

## Files That Must Not Be Modified

`docs/`, `agent-prompts/`, `spike/`.

## Implementation Tasks

### Task 1 — Project scaffold

`uv`-managed `pyproject.toml`. Dependencies pinned: `insightface`, `onnxruntime`,
`opencv-python-headless`, `numpy`, `Pillow`, `httpx`, `typer`, `rich`, `web3[tester]`,
`py-solc-x`, `eth-utils`. Dev: `pytest`, `pytest-cov`, `ruff`. Console script `facechain`.

Configure pytest: `markers = ["e2e: requires real external services"]` and default
`addopts = "-m 'not e2e'"` (per `05` §Layering).

### Task 2 — `errors.py`

The hierarchy from `02` §4, **verbatim, all seven classes**. Each carries an optional `context`
dict. `FaceChainError` is the base; no class outside this file inherits from `Exception` directly.

### Task 3 — `config.py`

The frozen `Config` dataclass from `02` §3.10 and `load_config(**overrides)`. This is the
**only** module in the project that reads `os.environ` (FR-054). Secrets are stored but their
`repr` is redacted — `Config` must be safe to log.

### Task 4 — `.env.example`

Every key documented, **no values**: `SERPAPI_KEY`, `IMGBB_KEY`, `RPC_URL`, `PRIVATE_KEY`,
`CONTRACT_ADDRESS`.

## Technical Constraints

TypeScript-style strictness does not apply, but per project standards: type hints on every
signature, PEP 8, `pathlib.Path` over `os.path`, f-strings, 100-char lines.

## Interfaces / Contracts

Exactly as `02` §3.10 and §4. Do not add fields to `Config` that no requirement needs.

## Error Handling

`load_config` raises `FaceChainError` with an actionable message when a required key for the
selected network is absent. Missing keys for *unused* features are not errors at load time.

## Performance Requirements

Import time under 200ms — no model loading at import. Models load lazily, on first use.

## Accuracy Requirements

None.

## Security Requirements

`Config.__repr__` redacts `private_key`, `serpapi_key`, `imgbb_key`. Test this (NFR-011).
`.env` git-ignored before the first commit containing it.

## Tests To Add

### Unit Tests
`test_config.py`: overrides beat environment; missing required key raises; **repr redacts all
three secrets**. `test_errors.py`: all seven classes exist, inherit correctly, carry context.

### Integration Tests
None.

### End-to-End Tests
None.

### Regression Tests
Full suite green.

### Failure Tests
Missing required key raises `FaceChainError`, not `KeyError`.

### Performance Tests
Import time asserted under 200ms.

### Accuracy Tests
None.

## Commands To Run

```bash
uv sync
uv run pytest -q
uv run ruff check .
uv run facechain --help
```

## Acceptance Criteria

| # | Criterion | Evidence |
|---|---|---|
| 1 | `uv sync` succeeds | command output |
| 2 | Suite green | pytest output |
| 3 | Seven exception classes exist | `test_errors.py` |
| 4 | `Config` repr redacts all secrets | `test_config.py` |
| 5 | `os.environ` appears only in `config.py` | `grep -rn "os.environ" src/` |
| 6 | `facechain --help` runs | command output |

## Exit Gate

```text
MILESTONE STATUS: PASS | BLOCKED | FAILED
```

## Failure Conditions

Any dependency unavailable on arm64; `os.environ` outside `config.py`; a secret visible in repr.

## Rollback Strategy

Delete `src/`, `tests/`, `pyproject.toml`. No other milestone depends on M01 yet.

## Documentation Updates

README skeleton with setup steps. `.agent-state/current-state.md`.

## Required Agent Report

Standard template.

## Questions That Require User Input

None expected.

## Definition of Done

All six criteria met, `ruff` clean, `.agent-state` updated.
