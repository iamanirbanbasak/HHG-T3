# 09 — Security & Privacy Hardening

Owned NFRs: NFR-011, NFR-012. Owning milestone: M15.

## Secrets

| Check | Method |
|---|---|
| `.env` is git-ignored | present in `.gitignore` from the first commit |
| `.env.example` contains no real values | audit sweep for key-shaped strings |
| no secret is committed anywhere in history | `git log -p` scan for key patterns |
| private key never logged | `test_security.py::test_no_secret_in_logs` captures all output |
| API keys never logged | same test; error messages name the *status*, never the key |
| secrets never in exception messages | reliability test 7 |

The repo holds a **funded testnet private key**. Low value, but a leaked key in a public
competition repo reads as carelessness to a reviewer. Treat it as real.

## Untrusted input

Candidate images are downloaded from arbitrary hosts. Treat every byte as hostile.

| Control | Setting |
|---|---|
| response size cap | `Config.max_image_bytes`, default 8 MiB, enforced **during** streaming, not after |
| request timeout | `Config.fetch_timeout_s`, default 10s, connect and read |
| content-type check | image types only, verified against actual bytes, not the header alone |
| decode safety | decode failures raise `CandidateFetchError`, never crash the run |
| redirect limit | bounded; no infinite redirect chains |
| URL scheme | https only; reject `file://`, `data:`, and internal addresses (SSRF) |
| temp files | created with `tempfile`, restrictive permissions, cleaned up |
| shell execution | none; no `subprocess` with untrusted input anywhere |

## Privacy

This project computes and stores **biometric data**. Say so, and minimise it.

- The evidence bundle stores the *digest* of the embedding, not the embedding itself.
- Raw artifacts stay local, under `artifacts/`, git-ignored except one sample run.
- Uploaded query crops expire after one day (FR-011).
- Nothing biometric is persisted beyond what verification requires.
- The README documents what is stored, where, for how long, and how to delete it.

Do not add persistence of face embeddings "for convenience". There is no requirement for it and
it enlarges the privacy surface for nothing.

## Ethical statements the README must carry

Verbatim in substance, from spec §15:

- The demo runs against a public figure with a large existing public footprint. The tool is not
  pointed at private individuals.
- Accuracy degrades across pose, lighting, age, occlusion, and demographic groups.
- A cosine score above threshold is **evidence of a probable match, not an identification**.
- The blockchain proves **when a claim was recorded and that it has not changed since**. It does
  not prove the claim is true. Anchoring a wrong match produces a permanent, tamper-evident
  record of a wrong match.
- Absence of a match is not evidence of absence of a social presence.

## Gate

M15 passes when every row above has a passing check, the git history scan is clean, and the
README privacy and ethics sections are complete.
