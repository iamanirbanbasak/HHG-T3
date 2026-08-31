"""Command-line interface. The only UI (the task requires no website).

This module presents; it does not compute. It is also the only place that constructs a Config.

Language discipline enforced here: a cosine similarity is NEVER rendered as a percentage or
labelled "confidence". 0.7123 is "cosine 0.7123", not "71% match".
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .config import load_config
from .errors import (
    ChainError,
    EvidenceIntegrityError,
    FaceChainError,
    NoFaceDetectedError,
    NoVerifiedMatchError,
    SearchProviderError,
)

app = typer.Typer(add_completion=False, help="Face scan -> social match -> on-chain evidence.")
console = Console()

EXIT_OK, EXIT_MISMATCH, EXIT_NO_FACE = 0, 1, 2
EXIT_PROVIDER, EXIT_NO_MATCH, EXIT_CHAIN = 3, 4, 5


def _load_dotenv() -> None:
    p = Path(".env")
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


def _cfg(network: str | None = None, threshold: float | None = None):
    _load_dotenv()
    return load_config(network=network, threshold=threshold)


def _fail(exc: FaceChainError, code: int) -> None:
    console.print(Panel(str(exc), title=f"[bold red]{type(exc).__name__}", border_style="red"))
    raise typer.Exit(code)


def _short(h: bytes | str) -> str:
    s = h.hex() if isinstance(h, bytes) else h
    return f"0x{s}" if not s.startswith("0x") else s


@app.command()
def scan(image: Path = typer.Option(..., "--image", "-i", exists=True)):
    """Detect a face and compute its embedding."""
    from .face.detect import detect_probe, load_image
    from .face.embed import embed, embedding_digest

    cfg = _cfg()
    try:
        probe, n = detect_probe(load_image(image))
        vec = embed(probe.aligned)
    except NoFaceDetectedError as exc:
        _fail(exc, EXIT_NO_FACE)
    except FaceChainError as exc:
        _fail(exc, EXIT_NO_FACE)

    t = Table(title="Face scan", show_header=False)
    t.add_row("faces detected", str(n))
    t.add_row("probe bbox", str(probe.bbox))
    t.add_row("detection score", f"{probe.det_score:.4f}")
    t.add_row("embedding", f"512-d, L2-normalised")
    t.add_row("embedding sha256", embedding_digest(vec)[:32] + "...")
    console.print(t)


@app.command()
def search(
    image: Path = typer.Option(..., "--image", "-i", exists=True),
    threshold: float = typer.Option(None, "--threshold"),
    network: str = typer.Option(None, "--network"),
):
    """Scan, reverse-image-search, and face-verify candidates (no anchoring)."""
    from .pipeline import run as run_pipeline

    cfg = _cfg(network, threshold)
    try:
        result = run_pipeline(image, cfg)
    except NoFaceDetectedError as exc:
        _fail(exc, EXIT_NO_FACE)
    except SearchProviderError as exc:
        _fail(exc, EXIT_PROVIDER)
    except NoVerifiedMatchError as exc:
        _fail(exc, EXIT_NO_MATCH)

    _print_result(result, cfg)


def _print_result(result, cfg) -> None:
    t = Table(title="Candidate verification")
    t.add_column("#"); t.add_column("post"); t.add_column("cosine", justify="right")
    t.add_column("vs threshold", justify="right")
    for i, s in enumerate(result.scored[:10], 1):
        ok = s.cosine >= cfg.threshold
        t.add_row(
            str(i), s.candidate.page_url[:60],
            f"{s.cosine:.4f}",
            f"[green]PASS" if ok else f"[dim]reject",
        )
    console.print(t)
    console.print(
        f"candidates={result.n_candidates}  social={result.n_social}  "
        f"face-verified={result.n_verified}  threshold={cfg.threshold} (cosine, not a percentage)"
    )
    console.print(Panel(f"[bold]{result.top.candidate.page_url}\n"
                        f"cosine similarity {result.top.cosine:.4f}",
                        title="Selected match", border_style="green"))


@app.command()
def run(
    image: Path = typer.Option(..., "--image", "-i", exists=True),
    network: str = typer.Option(None, "--network"),
    threshold: float = typer.Option(None, "--threshold"),
):
    """Full pipeline: scan -> search -> verify -> anchor on-chain."""
    from .chain.compile import compile_registry
    from .chain.deploy import deploy, make_web3
    from .chain.registry import Registry
    from .evidence import RECEIPT_JSON, evidence_hash, similarity_bps
    from .pipeline import run as run_pipeline

    cfg = _cfg(network, threshold)
    try:
        result = run_pipeline(image, cfg)
        _print_result(result, cfg)

        w3 = make_web3(cfg)
        if cfg.contract_address:
            abi, _ = compile_registry()
            reg = Registry(w3, cfg.contract_address, list(abi))
        else:
            addr = deploy(w3, cfg)
            abi, _ = compile_registry()
            reg = Registry(w3, addr, list(abi))
            console.print(f"deployed registry at {addr}")

        h = evidence_hash(result.bundle)
        rid, tx = reg.anchor(h, result.top.candidate.page_url,
                             similarity_bps(result.top.cosine))
        (result.run_dir / RECEIPT_JSON).write_text(json.dumps({
            "record_id": rid, "tx_hash": tx, "network": cfg.network,
            "contract_address": reg.address, "evidence_hash": h.hex(),
        }, indent=2))

        console.print(Panel(
            f"evidence hash  {_short(h)}\n"
            f"network        {cfg.network}\n"
            f"contract       {reg.address}\n"
            f"tx             {tx}\n"
            f"record id      {rid}\n"
            f"run dir        {result.run_dir}",
            title="Anchored on-chain", border_style="cyan"))
    except NoFaceDetectedError as exc:
        _fail(exc, EXIT_NO_FACE)
    except SearchProviderError as exc:
        _fail(exc, EXIT_PROVIDER)
    except NoVerifiedMatchError as exc:
        _fail(exc, EXIT_NO_MATCH)
    except ChainError as exc:
        _fail(exc, EXIT_CHAIN)


@app.command()
def verify(
    record_id: int = typer.Option(..., "--record-id"),
    run_dir: Path = typer.Option(..., "--run-dir", exists=True),
    network: str = typer.Option(None, "--network"),
    tamper: bool = typer.Option(False, "--tamper", help="Mutate source evidence to prove detection"),
):
    """Re-verify local evidence against the on-chain record."""
    from .chain.compile import compile_registry
    from .chain.deploy import make_web3
    from .chain.registry import Registry
    from .verify import verify_record

    cfg = _cfg(network)
    try:
        cfg.require("contract_address")
        w3 = make_web3(cfg)
        abi, _ = compile_registry()
        reg = Registry(w3, cfg.contract_address, list(abi))
        block = w3.eth.block_number
        res = verify_record(reg, record_id, run_dir, cfg, tamper=tamper)
    except ChainError as exc:
        _fail(exc, EXIT_CHAIN)
    except FaceChainError as exc:
        _fail(exc, EXIT_MISMATCH)

    body = (
        f"on-chain    {_short(res.onchain_hash)}   (block {block:,} - {res.network})\n"
        f"recomputed  {_short(res.recomputed_hash)}"
    )
    if res.matches:
        console.print(Panel(body + "\n\n[bold green]MATCH  record intact",
                            title="Verification", border_style="green"))
        raise typer.Exit(EXIT_OK)

    console.print(Panel(body + "\n\n[bold red]MISMATCH  evidence has been altered",
                        title="Verification" + (" (tamper demo)" if res.tampered else ""),
                        border_style="red"))
    # A mismatch is the expected, successful outcome of the tamper demonstration.
    raise typer.Exit(EXIT_OK if res.tampered else EXIT_MISMATCH)


@app.command()
def deploy(network: str = typer.Option(None, "--network")):
    """Deploy the FaceMatchRegistry contract."""
    from .chain.deploy import deploy as do_deploy, make_web3

    cfg = _cfg(network)
    try:
        addr = do_deploy(make_web3(cfg), cfg)
    except ChainError as exc:
        _fail(exc, EXIT_CHAIN)
    console.print(Panel(f"{addr}\nnetwork: {cfg.network}", title="Deployed", border_style="cyan"))


@app.command()
def anchor(
    run_dir: Path = typer.Option(..., "--run-dir", exists=True),
    network: str = typer.Option(None, "--network"),
):
    """Anchor an existing run's evidence bundle on-chain."""
    from .chain.compile import compile_registry
    from .chain.deploy import make_web3
    from .chain.registry import Registry
    from .evidence import RECEIPT_JSON, evidence_hash, rebuild_from_artifacts, similarity_bps

    cfg = _cfg(network)
    try:
        cfg.require("contract_address")
        bundle = rebuild_from_artifacts(run_dir)
        h = evidence_hash(bundle)
        w3 = make_web3(cfg)
        abi, _ = compile_registry()
        reg = Registry(w3, cfg.contract_address, list(abi))
        rid, tx = reg.anchor(h, bundle["match"]["post_url"],
                             similarity_bps(bundle["verification"]["cosine_similarity"]))
        (run_dir / RECEIPT_JSON).write_text(json.dumps({
            "record_id": rid, "tx_hash": tx, "network": cfg.network,
            "contract_address": reg.address, "evidence_hash": h.hex()}, indent=2))
    except ChainError as exc:
        _fail(exc, EXIT_CHAIN)
    except FaceChainError as exc:
        _fail(exc, EXIT_MISMATCH)
    console.print(Panel(f"record {rid}\ntx {tx}\nhash {_short(h)}",
                        title="Anchored", border_style="cyan"))


def main() -> None:  # pragma: no cover
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
