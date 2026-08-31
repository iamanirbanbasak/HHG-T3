# MASTER PROMPT — Generate the Complete FaceChain Agent Development System

You are the **lead software architect, senior Python engineer, ML engineer, blockchain engineer, QA engineer, performance engineer, security reviewer, and technical project manager** for this project.

The complete project specification is provided in:

`2026-08-31-face-chain-design.md`

## YOUR PRIMARY TASK

Read the **entire specification from beginning to end before generating anything**.

Then generate a complete set of **agent-executable Markdown development prompts** that can be used by one or more coding agents to build the entire project from an empty repository to a tested, demonstrable, submission-ready implementation.

The generated Markdown files are not merely documentation.

They are **execution contracts for coding agents**.

A competent coding agent should be able to open a milestone prompt, inspect the repository, execute the instructions, run the required tests, and know exactly when that milestone is complete.

---

# 1. SOURCE OF TRUTH

Treat `2026-08-31-face-chain-design.md` as the authoritative project specification.

Do not silently change architectural decisions from the specification.

Do not replace specified technologies with alternatives simply because you prefer them.

Do not invent requirements.

Do not remove requirements because they appear inconvenient.

If you believe a requirement or architectural decision should change, explicitly identify it as a **proposed deviation** and explain why.

The following are especially important and must remain load-bearing:

1. Face detection must actually occur.
2. Face embedding must actually be generated.
3. The embedding must materially participate in candidate verification.
4. The search cannot be a hardcoded/pre-selected result.
5. Search must perform a genuine reverse-image-search operation.
6. Candidates returned by search must be independently face-verified.
7. Candidate similarity must be calculated numerically.
8. Candidates below the configured threshold must be rejected.
9. The highest-scoring valid candidate is selected.
10. Evidence must be canonicalized deterministically.
11. The evidence bundle must be hashed.
12. The hash must be anchored on-chain.
13. Re-verification must retrieve the hash from the blockchain.
14. Re-verification must independently reconstruct the evidence from local artifacts.
15. The tamper demonstration must modify source evidence, not merely modify a digest.
16. The verification process must work without relying on the original hosted image URLs.
17. Provider errors must never be silently interpreted as "no results."
18. The implementation must remain CLI-only.
19. The system must clearly describe the result as probable-match evidence, not identity proof.

The source explicitly defines the load-bearing search design: the aligned face crop is searched, while every candidate is independently detected/embedded/scored.

---

# 2. FIRST DELIVERABLE: REQUIREMENTS INTELLIGENCE

Before generating implementation milestones, create:

`agent-prompts/00-requirements-intelligence.md`

This document must extract and organize the entire specification.

Include:

## 2.1 Functional requirements

Create IDs:

```text
FR-001
FR-002
...
```

For every functional requirement include:

- Requirement
- Source section
- Required behavior
- Implementation location
- Validation method
- Dependencies
- Risk

## 2.2 Non-functional requirements

Create IDs:

```text
NFR-001
NFR-002
...
```

Cover:

- latency
- accuracy
- reliability
- determinism
- testability
- security
- maintainability
- CLI usability
- offline verification
- reproducibility

## 2.3 Hard constraints

Explicitly identify constraints that must not be violated.

## 2.4 Non-goals

Explicitly identify functionality that should NOT be built.

## 2.5 Risks

Extract every important risk from the specification.

For each:

```text
Risk
Probability
Impact
Mitigation
Detection method
Fallback
Milestone where validated
```

## 2.6 Ambiguities

Identify requirements that require clarification.

Do not resolve important ambiguity silently.

---

# 3. SECOND DELIVERABLE: REQUIREMENTS TRACEABILITY

Create:

`agent-prompts/01-requirements-traceability.md`

Create a complete matrix:

| ID | Requirement | Component | Milestone | Test | Acceptance Criterion | Evidence |
|---|---|---|---|---|---|---|

Every hard requirement must eventually map to an objective test.

There must be no requirement that ends with:

> "Agent should verify manually."

Prefer executable validation.

---

# 4. THIRD DELIVERABLE: ARCHITECTURE EXECUTION PLAN

Create:

`agent-prompts/02-architecture-execution.md`

Use the architecture in the specification as the baseline.

Preserve the component boundaries:

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

The specification defines these as independently testable components with plain-data interfaces.

Document:

- component responsibilities
- interfaces
- dependency direction
- data flow
- error flow
- configuration flow
- artifact flow
- blockchain flow
- test boundaries
- performance-critical paths

Explicitly identify:

### Critical path

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

---

# 5. FOURTH DELIVERABLE: AGENT OPERATING CONTRACT

Create:

`agent-prompts/03-agent-operating-contract.md`

This is the universal instruction every coding agent must follow.

The agent must:

1. Read relevant requirements.
2. Inspect the repository.
3. Inspect existing implementation.
4. Inspect existing tests.
5. Never overwrite working code without understanding it.
6. Create a short implementation plan.
7. Implement incrementally.
8. Run focused tests.
9. Run regression tests.
10. Validate acceptance criteria.
11. Report evidence.
12. Update documentation.
13. Stop if blocked by a material decision.

Agents must distinguish:

```text
FACT
ASSUMPTION
IMPLEMENTATION DECISION
USER DECISION REQUIRED
RISK
TEST EVIDENCE
```

---

# 6. QUESTION PROTOCOL

Create:

`agent-prompts/04-question-protocol.md`

Agents must ask me questions when an unresolved issue materially affects:

- architecture
- correctness
- security
- privacy
- latency
- accuracy
- external service selection
- deployment
- cost
- demo feasibility
- interpretation of a hard requirement

Do NOT ask questions for trivial implementation choices.

When possible, present several options and a recommendation.

Use:

```text
## Decision Required

### Question
...

### Why it matters
...

### Recommended choice
...

### Option A
...

### Option B
...

### Consequence of each
...
```

If the decision is not material and a reversible assumption is safe, document the assumption and proceed.

---

# 7. MILESTONE GENERATION

Create a milestone directory:

```text
agent-prompts/milestones/
```

Generate enough milestones to make the project safely executable.

Use the following baseline milestones, but modify them if the requirements justify a better decomposition:

```text
M01 — Repository Foundation
M02 — Face Detection
M03 — Face Embedding & Similarity
M04 — Evidence & Deterministic Hashing
M05 — Blockchain Contract & Local Chain
M06 — Blockchain Deployment & Registry
M07 — Search Upload + Lens Integration
M08 — Candidate Filtering & Retrieval
M09 — Candidate Face Verification
M10 — End-to-End Pipeline
M11 — CLI & Demo Experience
M12 — Accuracy Calibration
M13 — Performance Optimization
M14 — Reliability & Failure Handling
M15 — Security & Privacy Hardening
M16 — Full Integration & Regression
M17 — Production/Demo Readiness
M18 — Final Submission Validation
```

Do not create artificial milestones merely to increase the number of files.

Every milestone must produce a meaningful increment.

---

# 8. EACH MILESTONE FILE MUST HAVE THE SAME STRUCTURE

Every milestone Markdown file must contain:

```text
# Milestone MXX — <Name>

## Objective

## Why This Milestone Exists

## Requirements Covered

## Preconditions

## Inputs

## Expected Repository State Before Starting

## Files To Create

## Files To Modify

## Files That Must Not Be Modified

## Implementation Tasks

### Task 1
### Task 2
### Task 3

## Technical Constraints

## Interfaces / Contracts

## Error Handling

## Performance Requirements

## Accuracy Requirements

## Security Requirements

## Tests To Add

### Unit Tests
### Integration Tests
### End-to-End Tests
### Regression Tests
### Failure Tests
### Performance Tests
### Accuracy Tests

## Commands To Run

## Acceptance Criteria

## Exit Gate

## Failure Conditions

## Rollback Strategy

## Documentation Updates

## Required Agent Report

## Questions That Require User Input

## Definition of Done
```

---

# 9. MILESTONE QUALITY RULE

A milestone is **NOT COMPLETE** because code exists.

A milestone is complete only when:

```text
Implementation
+
Tests
+
Validation
+
Acceptance criteria
+
Documentation
```

all pass.

Every milestone must end with an explicit gate:

```text
MILESTONE STATUS: PASS
```

or:

```text
MILESTONE STATUS: BLOCKED
```

or:

```text
MILESTONE STATUS: FAILED
```

Never allow an agent to silently continue after a failed gate.

---

# 10. TEST-FIRST PRIORITY

The specification explicitly identifies the evidence and tamper-verification tests as especially important.

Therefore, make the testing strategy deliberately front-loaded.

At minimum, preserve tests for:

- cosine similarity
- canonical JSON
- golden evidence hash
- candidate domain filtering
- candidate deduplication
- contract deployment
- contract anchoring
- contract readback
- empty hash rejection
- empty URL rejection
- successful re-verification
- tamper detection
- no verified match
- provider failure
- candidate fetch failure

Do not make external services mandatory for ordinary unit tests.

Mock external providers.

Use `eth-tester` for local blockchain integration tests.

Use real external services only in explicitly marked smoke/E2E tests.

---

# 11. FACE PIPELINE REQUIREMENTS

Create milestone instructions that preserve the specified face pipeline:

```text
input image
→ SCRFD detection
→ highest-scoring probe face
→ landmark alignment
→ 112×112 crop
→ ArcFace 512-dimensional embedding
→ L2 normalization
```

The interface must remain compatible with the specified design.

For multiple faces:

- choose the highest-scoring detection as the probe
- record the fact that multiple faces existed
- record the selected detection metadata

For zero faces:

```text
NoFaceDetectedError
```

must be raised.

Do not fabricate an embedding.

---

# 12. SEARCH REQUIREMENTS

The search implementation must preserve the distinction between:

### Query generation

The face embedding itself is not sent to Lens.

The aligned face crop is used as the primary visual query.

### Candidate verification

Each candidate image must undergo:

```text
fetch
→ detect
→ align
→ embed
→ cosine similarity
→ threshold
```

This distinction must be explicitly tested.

A test must fail if the embedding becomes decorative.

The pipeline must perform:

```text
Lens(face crop)
+
Lens(full image)
→ union
→ social-domain filtering
→ deduplication
→ candidate verification
→ ranking
```

The full-photo query exists to increase recall, not to bypass face verification.

---

# 13. NO-HARDCODING REQUIREMENT

Create dedicated tests and final-review instructions that search the repository for evidence of hardcoded results.

The shipped implementation must not contain:

- a pre-selected social-media result
- a pre-selected candidate URL
- fake provider output used as the actual search result
- logic that automatically chooses a known demo result
- hidden fixtures masquerading as live search results

Development mocks are allowed only when clearly isolated from production execution.

The final E2E path must demonstrate a genuine external search.

---

# 14. EVIDENCE INTEGRITY REQUIREMENTS

Preserve the canonical serialization:

```text
json.dumps(
    obj,
    sort_keys=True,
    separators=(",", ":"),
    ensure_ascii=True
).encode("utf-8")
```

The evidence layer must have deterministic behavior.

Artifact digests:

```text
SHA-256
```

On-chain bundle hash:

```text
keccak256
```

Do not merge these algorithms into one.

The milestone prompts must include golden tests proving serialization stability.

---

# 15. BLOCKCHAIN REQUIREMENTS

Preserve the minimal append-only registry design from the specification.

Support:

```text
local
eth-tester
```

and:

```text
base-sepolia
```

through configuration.

The blockchain abstraction must remain provider-agnostic.

Network selection should occur at the configuration boundary rather than throughout business logic.

Test:

```text
compile
→ deploy
→ anchor
→ read
→ count
→ verify
```

The agent must never claim that blockchain anchoring proves the underlying face match is true.

It proves the integrity/timestamp of the recorded claim.

---

# 16. RE-VERIFICATION REQUIREMENTS

This is a critical milestone and must receive special attention.

`verify` must:

1. Read the evidence hash from the blockchain.
2. Read source artifacts from local disk.
3. Recalculate artifact hashes.
4. Rebuild the evidence bundle.
5. Canonicalize it.
6. Recalculate the bundle hash.
7. Compare local and on-chain values.
8. Display both hashes.
9. Display network and block information.
10. Clearly report MATCH or MISMATCH.

The verifier must NOT:

```text
download the original candidate again
```

or:

```text
download the expired query image again
```

or:

```text
load the stored evidence hash and compare it against itself
```

The specification explicitly requires the recomputation to use local artifacts and only the blockchain RPC as the external read.

---

# 17. TAMPER TEST

Create a first-class test for:

```text
verify --tamper
```

The command must:

1. Copy the artifact directory to a temporary location.
2. Modify one byte of source evidence.
3. Rebuild the bundle.
4. Recalculate the hash.
5. Compare it against the original on-chain hash.
6. Produce a mismatch.
7. Leave the original artifacts untouched.

The test must prove that the mutation happens at the source-evidence level.

It must NOT simply modify the stored hash.

The expected behavior is:

```text
on-chain    0x...
recomputed  0x...
MISMATCH    evidence has been altered
```

---

# 18. PERFORMANCE ENGINEERING

Create:

`agent-prompts/06-performance-engineering.md`

Performance must be measured rather than guessed.

Focus optimization on the actual critical path.

Measure, where applicable:

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

Track:

```text
p50
p95
p99
```

where meaningful.

Optimize without sacrificing correctness.

Potential optimization areas include:

- model warm-up
- model reuse
- connection pooling
- HTTP timeouts
- concurrent candidate fetching
- bounded concurrency
- image-size limits
- avoiding repeated embeddings
- caching within a run
- avoiding redundant serialization
- efficient artifact handling

Do not introduce unbounded concurrency.

Do not optimize by removing verification.

Do not optimize by reducing accuracy without documenting the tradeoff.

---

# 19. ACCURACY ENGINEERING

Create:

`agent-prompts/07-accuracy-engineering.md`

The threshold must remain configurable.

The specified default of `0.45` must be treated as an operating point to validate rather than an unquestionable probability or confidence value.

Create a labelled evaluation set where feasible.

Measure:

```text
same-identity similarity
different-identity similarity
false positives
false negatives
threshold separation
```

Do not describe cosine similarity as probability.

Do not describe:

```text
0.7123
```

as:

```text
71.23% confidence
```

The system must describe it as a cosine similarity score.

Record threshold validation results in the README.

---

# 20. RELIABILITY ENGINEERING

Create:

`agent-prompts/08-reliability-engineering.md`

Explicitly test:

- no face
- multiple faces
- malformed image
- provider timeout
- provider 4xx
- provider 5xx
- invalid API key
- empty search results
- candidate image 403
- candidate image timeout
- malformed candidate image
- no verified candidate
- RPC failure
- transaction revert
- missing contract
- corrupted artifact
- missing artifact
- tampered artifact

Preserve the distinction:

```text
provider failure
≠
legitimate empty result
```

The source explicitly requires this distinction.

---

# 21. SECURITY & PRIVACY

Create:

`agent-prompts/09-security-hardening.md`

Validate:

- secrets never committed
- `.env` ignored
- `.env.example` contains no secrets
- private keys never logged
- API keys never logged
- URLs handled safely
- untrusted image input handled safely
- downloaded content constrained
- timeouts configured
- response sizes constrained
- temporary files handled safely
- shell execution avoided unless required
- blockchain private-key handling reviewed

Explicitly document privacy implications of face embeddings and downloaded social-media evidence.

Do not introduce unnecessary persistence of biometric data.

---

# 22. CLI / DEMO ENGINEERING

The CLI is the only UI.

Create milestone instructions ensuring:

```text
scan
search
anchor
verify
run
deploy
```

are coherent and usable.

The demo must be legible in a screen recording.

Use Rich output to show:

- current stage
- candidate count
- face verification score
- threshold
- selected match
- evidence hash
- network
- transaction hash
- verification result

Never label cosine similarity as confidence percentage.

---

# 23. END-TO-END DEMO

Create a dedicated milestone:

`M17-demo-readiness.md`

The demo must exercise the actual path:

```text
real input
→ real face detection
→ real embedding
→ real search provider
→ real candidate retrieval
→ real candidate face verification
→ real evidence bundle
→ real blockchain anchor
→ real blockchain read
→ real local recomputation
→ successful verification
→ tamper demonstration
```

Do not substitute mocked services in the final recording.

If an external dependency prevents the demonstration, report it as a blocker.

---

# 24. NEGATIVE PATH

The demo/test strategy must also contain a negative path.

Use the secondary scenario described in the specification to demonstrate that the system can legitimately produce:

```text
no verified match
```

or:

```text
low-confidence / rejected candidates
```

without fabricating a result.

Do not force every input to produce a match.

---

# 25. DEADLINE-AWARE EXECUTION

The specification contains a seven-day schedule and explicitly identifies the search leg as the highest external feasibility risk.

Create:

`agent-prompts/10-deadline-plan.md`

Prioritize work according to:

```text
highest uncertainty first
highest grading risk first
highest architectural dependency first
```

The external search feasibility spike must happen early.

Do not spend days polishing deterministic components before confirming that genuine Lens/social search can work for the intended demo subject.

---

# 26. FINAL AUDIT AGENT

Create:

`agent-prompts/99-final-audit.md`

This is a special prompt for a fresh agent who has **not written the project**.

Its job is to act as an adversarial reviewer.

It must inspect:

- requirements
- source tree
- tests
- configuration
- README
- contracts
- CLI
- artifacts
- search implementation
- face verification
- blockchain verification

It must specifically attempt to detect:

### Requirement cheating

- hardcoded candidate
- decorative embedding
- mocked search in production
- fake blockchain verification
- self-comparison
- tamper test that edits hashes instead of evidence
- fabricated confidence
- swallowed provider errors

### Engineering weaknesses

- race conditions
- unbounded concurrency
- poor timeouts
- resource leaks
- secret leakage
- brittle parsing
- insufficient tests
- non-deterministic hashing
- broken offline verification

### Submission risks

- README omissions
- missing commands
- broken fresh-install experience
- missing `.env.example`
- missing deployment instructions
- missing explorer link
- unclear limitations
- misleading identity claims

The final auditor must produce:

```text
PASS
PASS WITH WARNINGS
BLOCKED
FAIL
```

and provide evidence for every finding.

---

# 27. FINAL VALIDATION MATRIX

Create:

`agent-prompts/FINAL_VALIDATION.md`

Include one executable checklist for every requirement.

Example:

```text
[ ] R1 face detected
[ ] R1 embedding generated
[ ] R2 genuine search executed
[ ] R2 social candidate discovered dynamically
[ ] R2 candidate face independently verified
[ ] R2 similarity threshold applied
[ ] R3 evidence hashed
[ ] R3 hash anchored
[ ] R3 hash read from chain
[ ] R3 local evidence independently recomputed
[ ] R3 tamper mutation causes mismatch
[ ] C1 no web application required
[ ] C2 README complete
[ ] no hardcoded production result
[ ] provider errors distinguishable from empty results
[ ] local verification works without social-media access
[ ] tests pass
[ ] performance checks pass
[ ] accuracy checks pass
[ ] security checks pass
```

For each checkbox provide:

```text
Requirement
Evidence
Command
Expected result
Actual result
Status
```

---

# 28. GENERATED FILE STRUCTURE

Generate this complete structure:

```text
agent-prompts/
│
├── 00-requirements-intelligence.md
├── 01-requirements-traceability.md
├── 02-architecture-execution.md
├── 03-agent-operating-contract.md
├── 04-question-protocol.md
├── 05-testing-strategy.md
├── 06-performance-engineering.md
├── 07-accuracy-engineering.md
├── 08-reliability-engineering.md
├── 09-security-hardening.md
├── 10-deadline-plan.md
│
├── milestones/
│   ├── M01-repository-foundation.md
│   ├── M02-face-detection.md
│   ├── M03-face-embedding-similarity.md
│   ├── M04-evidence-hashing.md
│   ├── M05-blockchain-local.md
│   ├── M06-blockchain-deployment.md
│   ├── M07-search-uploader-lens.md
│   ├── M08-candidate-filtering.md
│   ├── M09-candidate-face-verification.md
│   ├── M10-end-to-end-pipeline.md
│   ├── M11-cli-demo.md
│   ├── M12-accuracy-calibration.md
│   ├── M13-performance-optimization.md
│   ├── M14-reliability.md
│   ├── M15-security.md
│   ├── M16-full-regression.md
│   ├── M17-demo-readiness.md
│   └── M18-final-submission.md
│
└── 99-final-audit.md
```

Modify this structure when the actual dependency graph warrants it.

---

# 29. AGENT HANDOFF PROTOCOL

Every milestone must leave behind enough information for another agent to continue.

At completion, write/update a project state document:

```text
.agent-state/current-state.md
```

It should contain:

```text
Current milestone
Completed milestones
Current branch/state
Implemented components
Known failures
Known risks
Assumptions
Open decisions
Test status
Performance measurements
Accuracy measurements
Next milestone
```

Never rely on conversational memory for project-critical state.

---

# 30. CODE QUALITY RULES

Agents should favor:

- explicit interfaces
- small modules
- deterministic functions
- dependency injection
- typed configuration
- domain-specific exceptions
- clear boundaries
- testable code
- minimal dependencies
- bounded resource usage
- structured logging
- meaningful error messages

Avoid:

- global mutable state
- hidden environment access
- duplicated provider logic
- giant functions
- silent exception handling
- unnecessary abstractions
- premature frameworks
- unnecessary services

The source already specifies configuration should be constructed once and passed through the system rather than having modules directly read environment variables. Preserve that design.

---

# 31. IMPORTANT: DO NOT OVERWRITE THE SPECIFICATION

If the source says:

```text
Use X
```

do not silently change it to:

```text
Use Y
```

If the agent discovers that X is impossible in the target environment:

1. Document the problem.
2. Run a minimal feasibility test.
3. Ask the user if the decision is material.
4. Propose alternatives.
5. Do not silently rewrite the architecture.

---

# 32. IMPORTANT: OPTIMIZE FOR THE ACTUAL GRADING CLAIM

The project is not simply:

```text
face recognition + blockchain
```

The core demonstrable claim is:

```text
A face-derived query produces dynamically discovered web candidates,
those candidates are independently face-verified,
the selected evidence is deterministically hashed,
the hash is recorded on-chain,
and the evidence can later be independently recomputed and compared
against the blockchain record.
```

Every milestone should strengthen this claim.

Any implementation that makes one of these steps decorative, simulated, self-referential, or hardcoded must be treated as a failure.

---

# 33. OUTPUT REQUIREMENT

Your output from this generation task must be the **complete set of Markdown files**, not merely a high-level plan.

Each Markdown file must be ready to save directly into the repository.

Do not omit difficult milestones.

Do not replace implementation instructions with vague statements such as:

> "Implement the required functionality."

Instead specify:

- what the agent must inspect
- what it must create
- what interfaces it must implement
- what tests it must write
- what commands it must run
- what outputs it must observe
- what constitutes failure
- what constitutes success
- when it should ask the user

---

# 34. FINAL PRINCIPLE

Build the project in small, independently verifiable increments.

At every stage:

```text
UNDERSTAND
    ↓
PLAN
    ↓
IMPLEMENT
    ↓
TEST
    ↓
MEASURE
    ↓
REVIEW
    ↓
PASS / BLOCK
    ↓
NEXT MILESTONE
```

Never:

```text
UNDERSTAND
    ↓
WRITE EVERYTHING
    ↓
HOPE IT WORKS
```

The finished project must be **correct, measurable, reproducible, low-latency, accuracy-conscious, secure, testable, explainable, and genuinely demonstrable**.

When the requirements are insufficient to make a material decision, ask the user rather than inventing an answer.

When the requirements are sufficient, proceed autonomously.