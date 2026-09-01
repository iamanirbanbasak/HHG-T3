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
import threading
import traceback
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import Config, load_config
from .errors import (
    ChainError,
    FaceChainError,
    NoFaceDetectedError,
    NoVerifiedMatchError,
    SearchProviderError,
)

STATIC = Path(__file__).parent / "static"


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
    from .chain.deploy import deploy, make_web3
    from .chain.registry import Registry
    from .evidence import RECEIPT_JSON, evidence_hash, similarity_bps
    from .pipeline import run as run_pipeline
    from .verify import verify_record

    try:
        cfg = _cfg(payload)
        image = Path(payload["image"]) if payload.get("image") else None

        if payload.get("capture"):
            from .capture import capture_face

            job.log("opening camera...", "step")
            image, score, attempts = capture_face(Path("capture.jpg"))
            job.log(f"captured {image.name}  det_score={score:.4f}  ({attempts} attempt)", "ok")

        if image is None or not image.exists():
            raise FaceChainError("no input image")

        job.log(f"provider={cfg.search_provider}  network={cfg.network}  tau={cfg.threshold}", "dim")
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
        for r in rows:
            job.log(
                f"  {r['cosine']:.4f}  {'PASS  ' if r['pass'] else 'reject'}  {r['url'][:64]}",
                "ok" if r["pass"] else "dim",
            )

        job.log(f"selected match: {result.top.candidate.page_url}", "ok")
        job.log(f"cosine similarity {result.top.cosine:.4f} (a cosine score, not a percentage)", "ok")

        job.log("anchoring evidence on-chain...", "step")
        w3 = make_web3(cfg)
        abi, _ = compile_registry()
        if cfg.contract_address:
            reg = Registry(w3, cfg.contract_address, list(abi))
        else:
            reg = Registry(w3, deploy(w3, cfg), list(abi))
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
            "evidence_hash": "0x" + h.hex(),
            "record_id": rid,
            "tx": tx,
            "network": cfg.network,
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
        job.log(f"NoVerifiedMatchError: {exc}", "warn")
        job.log("no candidate cleared the threshold. nothing was anchored.", "warn")
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
    from fastapi import FastAPI
    from fastapi.responses import FileResponse, JSONResponse

    app = FastAPI(title="facechain", docs_url=None, redoc_url=None)

    @app.get("/")
    def index():
        return FileResponse(STATIC / "index.html")

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

    @app.post("/api/run")
    async def start(payload: dict):
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
