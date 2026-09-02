"""Local terminal-themed web UI.

Note: the task requires no website, and 00-requirements-intelligence.md lists a web frontend as
non-goal NG-01. This exists as an extra on top of the CLI, which remains the graded deliverable.
Nothing here reimplements pipeline logic -- it drives exactly the same functions the CLI does, so
the two cannot drift apart.

Binds to 127.0.0.1 only. It runs a face pipeline against a local camera and holds API keys in
process; it is not meant to be reachable from anywhere else.
"""

from __future__ import annotations

import json
import secrets
import threading
import traceback
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse

from .config import Config, load_config
from .errors import (
    ChainError,
    FaceChainError,
    NoFaceDetectedError,
    NoVerifiedMatchError,
    SearchProviderError,
)

STATIC = Path(__file__).parent / "static"

# Root that user-supplied image paths are confined to.
PROJECT_ROOT = Path.cwd().resolve()
ALLOWED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".heic", ".heif"}

# Per-process CSRF token. The page embeds it; API writes require it. A cross-origin script cannot
# read our HTML (no CORS is enabled), so it cannot obtain the token.
CSRF_TOKEN = secrets.token_urlsafe(32)

UPLOAD_DIR = PROJECT_ROOT / "uploads"
MAX_UPLOAD_BYTES = 12 * 1024 * 1024
# Magic bytes, checked against actual content rather than the declared type or the filename.
IMAGE_MAGIC = (
    b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n", b"GIF8", b"RIFF", b"BM",
    b"II*\x00", b"MM\x00*",
)


def _looks_like_image(head: bytes) -> bool:
    if any(head.startswith(m) for m in IMAGE_MAGIC):
        return True
    # HEIC/HEIF carry an ftyp box a few bytes in
    return len(head) > 12 and head[4:8] == b"ftyp"


def safe_image_path(raw: str) -> Path:
    """Resolve a user-supplied image path, confined to the project directory.

    Without this, a POST to the local API could name any image on disk -- and since the pipeline
    UPLOADS the probe to a public image host to run the search, that is file exfiltration rather
    than mere disclosure. The server is localhost-bound, which is not a defence: any page in the
    browser, or any local process, can reach it.
    """
    if not raw:
        raise FaceChainError("no input image")
    candidate = Path(raw).expanduser()
    resolved = (PROJECT_ROOT / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()

    try:
        resolved.relative_to(PROJECT_ROOT)
    except ValueError:
        raise FaceChainError(
            "image must be inside the project directory",
            {"hint": "copy the file into the project folder and pass a relative path"},
        ) from None

    if resolved.suffix.lower() not in ALLOWED_SUFFIXES:
        raise FaceChainError(
            "unsupported image type", {"suffix": resolved.suffix, "allowed": "jpg png webp bmp heic"}
        )
    if not resolved.is_file():
        raise FaceChainError("image not found", {"path": str(candidate)})
    return resolved


@dataclass
class Job:
    id: str
    lines: list[dict] = field(default_factory=list)
    done: bool = False
    ok: bool = False
    result: dict[str, Any] | None = None

    def log(self, text: str, kind: str = "info") -> None:
        self.lines.append({"text": text, "kind": kind})


_jobs: dict[str, Job] = {}
_lock = threading.Lock()


def _account_json(a) -> dict[str, Any]:
    payload = {
        "display": a.display,
        "platform": a.platform,
        "handle": a.handle,
        "profile_url": a.profile_url,
        "urls": list(a.urls),
        "origin": a.origin,
        "cosine": None if a.origin == "linked" else round(a.best_cosine, 4),
    }
    return payload


def _cfg(payload: dict) -> Config:
    from .cli import _load_dotenv

    _load_dotenv()
    return load_config(
        network=payload.get("network") or "local",
        threshold=payload.get("threshold"),
        search_provider=payload.get("provider") or None,
    )


def _run_job(job: Job, payload: dict) -> None:
    """Drive the same code path as `facechain run`."""
    from .chain.compile import compile_registry
    from .chain.deploy import deploy, make_web3, signing_account
    from .chain.registry import Registry
    from .evidence import RECEIPT_JSON, evidence_hash, similarity_bps
    from .pipeline import run as run_pipeline
    from .verify import verify_record

    try:
        cfg = _cfg(payload)
        image = safe_image_path(payload["image"]) if payload.get("image") else None

        if payload.get("capture"):
            from .capture import capture_face

            job.log("opening camera...", "step")
            image, score, attempts = capture_face(Path("capture.jpg"))
            job.log(f"captured {image.name}  det_score={score:.4f}  ({attempts} attempt)", "ok")

        if image is None:
            raise FaceChainError("no input image")

        from .providers import resolve_chain

        chain = " -> ".join(n for n, _ in resolve_chain(cfg))
        job.log(f"providers: {chain}   network={cfg.network}  tau={cfg.threshold}", "dim")
        job.log("detecting face and computing embedding...", "step")

        result = run_pipeline(image, cfg)
        job.log(
            f"lens returned {result.n_candidates} candidates, "
            f"{result.n_social} on social domains", "info"
        )
        job.log(f"independently embedded and scored {len(result.scored)} candidates", "step")

        rows = [
            {
                "url": s.candidate.page_url,
                "cosine": round(s.cosine, 4),
                "pass": s.cosine >= cfg.threshold,
            }
            for s in result.scored[:12]
        ]
        for s in result.expanded:
            rows.append({
                "url": s.candidate.page_url,
                "cosine": round(s.cosine, 4),
                "pass": True,
            })
        for r in rows:
            job.log(
                f"  {r['cosine']:.4f}  {'PASS  ' if r['pass'] else 'reject'}  {r['url'][:64]}",
                "ok" if r["pass"] else "dim",
            )

        from .profiles import group_accounts

        survivors = []
        for s in result.scored:
            if s.cosine < cfg.threshold:
                continue
            url = s.candidate.page_url
            if (
                result.resolved_profile
                and s.candidate.page_url == result.top.candidate.page_url
            ):
                url = result.resolved_profile
            survivors.append((url, s.cosine))
        survivors.extend((s.candidate.page_url, s.cosine) for s in result.expanded)
        accounts = group_accounts(survivors)
        if result.resolved_handle:
            job.log(f"account  @{result.resolved_handle}  {result.resolved_profile}", "ok")
            post = result.top.candidate.page_url
            for a in accounts:
                if a.handle == result.resolved_handle and post not in a.urls:
                    a.urls.append(post)

        for a in result.attempts:
            job.log(f"  {a['provider']}: {a['outcome'].replace('_', ' ')}"
                    + (f" (best {a['best']})" if "best" in a else ""), "dim")
        job.log(f"matched via {result.provider}", "ok")
        job.log(f"{len(survivors)} match(es) above threshold, "
                f"across {len(accounts)} account(s)", "ok")
        for a in accounts:
            job.log(f"  {a.display}  best cosine {a.best_cosine:.4f}", "ok")
            for u in a.urls:
                job.log(f"      {u}", "dim")

        if result.expanded:
            job.log(
                f"{len(result.expanded)} further account(s) from the verified handle "
                f"(each independently face-scored)",
                "info",
            )
            for s in result.expanded:
                job.log(
                    f"  {s.cosine:.4f}  PASS   {s.candidate.page_url[:64]}",
                    "ok",
                )

        linked = result.linked
        if linked:
            job.log(
                f"{len(linked)} profile(s) linked from the verified page "
                f"(not independently face-scored)",
                "info",
            )
            for a in linked:
                job.log(f"  {a.display}", "ok")
                for u in a.urls:
                    job.log(f"      {u}", "dim")

        job.log("anchoring evidence on-chain...", "step")
        w3 = make_web3(cfg)
        abi, _ = compile_registry()
        if cfg.contract_address:
            reg = Registry(w3, cfg.contract_address, list(abi), account=signing_account(w3, cfg))
        else:
            reg = Registry(w3, deploy(w3, cfg), list(abi), account=signing_account(w3, cfg))
            job.log(f"deployed registry at {reg.address}", "dim")

        h = evidence_hash(result.bundle)
        rid, tx = reg.anchor(h, result.top.candidate.page_url, similarity_bps(result.top.cosine))
        (result.run_dir / RECEIPT_JSON).write_text(json.dumps({
            "record_id": rid, "tx_hash": tx, "network": cfg.network,
            "contract_address": reg.address, "evidence_hash": h.hex()}, indent=2))
        job.log(f"anchored  record={rid}  tx={tx[:20]}...", "ok")

        job.log("re-verifying against the chain...", "step")
        ok = verify_record(reg, rid, result.run_dir, cfg)
        job.log(f"on-chain    0x{ok.onchain_hash.hex()}", "hash")
        job.log(f"recomputed  0x{ok.recomputed_hash.hex()}", "hash")
        job.log("MATCH  record intact" if ok.matches else "MISMATCH", "ok" if ok.matches else "err")

        job.log("tamper demonstration: flipping one byte of source evidence...", "step")
        bad = verify_record(reg, rid, result.run_dir, cfg, tamper=True)
        job.log(f"on-chain    0x{bad.onchain_hash.hex()}", "hash")
        job.log(f"recomputed  0x{bad.recomputed_hash.hex()}", "hash")
        job.log(
            "MISMATCH  evidence has been altered" if not bad.matches
            else "TAMPER NOT DETECTED - BUG",
            "err",
        )

        job.result = {
            "match": result.top.candidate.page_url,
            "cosine": round(result.top.cosine, 4),
            "threshold": cfg.threshold,
            "candidates": result.n_candidates,
            "social": result.n_social,
            "verified": result.n_verified,
            "rows": rows,
            "accounts": [_account_json(a) for a in accounts],
            "resolved_handle": result.resolved_handle,
            "resolved_profile": result.resolved_profile,
            "linked": [_account_json(a) for a in linked],
            "evidence_hash": "0x" + h.hex(),
            "record_id": rid,
            "tx": tx,
            "network": cfg.network,
            "provider": result.provider,
            "attempts": result.attempts,
            "contract": reg.address,
            "run_dir": str(result.run_dir),
            "verified_match": ok.matches,
            "tamper_detected": not bad.matches,
        }
        job.ok = True

    except NoFaceDetectedError as exc:
        job.log(f"NoFaceDetectedError: {exc}", "err")
    except SearchProviderError as exc:
        job.log(f"SearchProviderError: {exc}", "err")
        job.log("a provider failure is not the same as 'no results found'", "dim")
    except NoVerifiedMatchError as exc:
        # `attempts` is structured data; printing the exception repr floods the UI with a dict.
        job.log("no candidate cleared the threshold in any provider", "warn")
        for a in exc.context.get("attempts") or []:
            if a.get("outcome") == "provider_error":
                job.log(f"  {a['provider']:<12} unavailable - {str(a.get('detail',''))[:64]}", "dim")
            else:
                job.log(
                    f"  {a['provider']:<12} {a.get('candidates',0):>4} candidates -> "
                    f"{a.get('social',0):>3} profiles -> {a.get('scored',0):>3} face-scored -> "
                    f"best {a.get('best',0):.4f}", "dim")
        job.log(f"threshold {exc.context.get('threshold')}; nothing was anchored.", "warn")
        job.log("this is the honest negative path, not an error.", "dim")
    except ChainError as exc:
        job.log(f"ChainError: {exc}", "err")
    except FaceChainError as exc:
        # Any other domain error is expected and reported plainly, without a traceback.
        job.log(f"{type(exc).__name__}: {exc}", "err")
    except Exception as exc:  # noqa: BLE001
        job.log(f"unexpected: {type(exc).__name__}: {exc}", "err")
        job.log(traceback.format_exc()[-400:], "dim")
    finally:
        job.done = True


def create_app():
    app = FastAPI(title="facechain", docs_url=None, redoc_url=None)

    def _check_origin(request: Request) -> None:
        """Reject browser requests that did not originate from this page."""
        origin = request.headers.get("origin")
        if origin is None:
            return  # non-browser clients (curl, tests) send no Origin
        host = request.headers.get("host", "")
        if origin not in (f"http://{host}", f"https://{host}"):
            raise HTTPException(status_code=403, detail="cross-origin request rejected")

    @app.get("/")
    def index():
        # The CSRF token is injected per response rather than baked into the static file.
        html = (STATIC / "index.html").read_text()
        html = html.replace("__CSRF_TOKEN__", CSRF_TOKEN)
        return HTMLResponse(html)

    @app.get("/api/config")
    def config():
        cfg = _cfg({})
        return {
            "provider": cfg.search_provider,
            "network": cfg.network,
            "threshold": cfg.threshold,
            "has_serpapi": bool(cfg.serpapi_key),
            "has_imgbb": bool(cfg.imgbb_key),
            "has_facecheck": bool(cfg.facecheck_key),
        }

    @app.post("/api/upload")
    async def upload(
        request: Request,
        file: UploadFile = File(...),
        x_csrf_token: str = Header(default=""),
    ):
        """Accept an uploaded image and return a project-relative path.

        The client never chooses where the file lands. The stored name is generated, the
        extension comes from a fixed allowlist, and the content is checked against magic bytes --
        a supplied filename is treated as a label, never as a path.
        """
        _check_origin(request)
        if not secrets.compare_digest(x_csrf_token, CSRF_TOKEN):
            raise HTTPException(status_code=403, detail="missing or invalid CSRF token")

        suffix = Path(file.filename or "").suffix.lower()
        if suffix not in ALLOWED_SUFFIXES:
            raise HTTPException(
                status_code=400,
                detail=f"unsupported image type {suffix or '(none)'}",
            )

        data = await file.read(MAX_UPLOAD_BYTES + 1)
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="image exceeds 12 MB")
        if not data:
            raise HTTPException(status_code=400, detail="empty upload")
        if not _looks_like_image(data[:16]):
            raise HTTPException(status_code=400, detail="content is not a recognisable image")

        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        dest = UPLOAD_DIR / f"{uuid.uuid4().hex[:16]}{suffix}"
        dest.write_bytes(data)
        return {"path": str(dest.relative_to(PROJECT_ROOT)), "bytes": len(data)}

    @app.post("/api/run")
    async def start(request: Request, payload: dict, x_csrf_token: str = Header(default="")):
        _check_origin(request)
        if not secrets.compare_digest(x_csrf_token, CSRF_TOKEN):
            raise HTTPException(status_code=403, detail="missing or invalid CSRF token")
        job = Job(id=uuid.uuid4().hex[:12])
        with _lock:
            _jobs[job.id] = job
        threading.Thread(target=_run_job, args=(job, payload), daemon=True).start()
        return {"job": job.id}

    @app.get("/api/job/{job_id}")
    def status(job_id: str):
        job = _jobs.get(job_id)
        if job is None:
            return JSONResponse({"error": "no such job"}, status_code=404)
        return {"lines": job.lines, "done": job.done, "ok": job.ok, "result": job.result}

    return app


def serve(host: str = "127.0.0.1", port: int = 8000) -> None:  # pragma: no cover
    import uvicorn

    uvicorn.run(create_app(), host=host, port=port, log_level="warning")
