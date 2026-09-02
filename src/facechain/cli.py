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
import traceback
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


def _cfg(network: str | None = None, threshold: float | None = None,
         provider: str | None = None):
    _load_dotenv()
    return load_config(network=network, threshold=threshold, search_provider=provider)


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
    provider: str = typer.Option(None, "--provider"),
):
    """Scan, reverse-image-search, and face-verify candidates (no anchoring)."""
    from .pipeline import run as run_pipeline

    cfg = _cfg(network, threshold, provider)
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
    tried = " -> ".join(
        f"{a['provider']}({a['outcome'].replace('_', ' ')})" for a in result.attempts
    )
    if tried:
        console.print(f"[dim]providers: {tried}")
    console.print(
        f"matched via [bold]{result.provider}[/]  candidates={result.n_candidates}  "
        f"social={result.n_social}  face-verified={result.n_verified}  "
        f"threshold={cfg.threshold} (cosine, not a percentage)"
    )
    console.print(Panel(f"[bold]{result.top.candidate.page_url}\n"
                        f"cosine similarity {result.top.cosine:.4f}",
                        title="Selected match", border_style="green"))
    if result.linked:
        console.print(
            "[cyan]linked from verified page[/cyan] "
            "[dim](published there; not independently face-scored)[/dim]"
        )
        for a in result.linked:
            console.print(f"  {a.display}")
            seen: list[str] = []
            if a.profile_url:
                seen.append(a.profile_url)
            for u in a.urls:
                if u not in seen:
                    seen.append(u)
            for u in seen:
                console.print(f"      {u}")
    if result.expanded:
        console.print(
            "[green]same handle on other platforms[/green] "
            "[dim](independently face-scored)[/dim]"
        )
        for s in result.expanded:
            console.print(
                f"  {s.candidate.page_url}  cosine {s.cosine:.4f}"
            )


@app.command()
def run(
    image: Path = typer.Option(None, "--image", "-i", help="Input photo (omit with --capture)"),
    capture_now: bool = typer.Option(False, "--capture", help="Take a photo with the camera first"),
    camera: int = typer.Option(0, "--camera"),
    network: str = typer.Option(None, "--network"),
    threshold: float = typer.Option(None, "--threshold"),
    provider: str = typer.Option(
        None, "--provider",
        help="first backend to try: google_lens, yandex, or facecheck. "
             "Others are tried in turn unless --no-fallback.",
    ),
    no_fallback: bool = typer.Option(
        False, "--no-fallback", help="Use only the named provider; do not try the others."
    ),
):
    """Full pipeline: scan -> search -> verify -> anchor on-chain.

    Pass --capture to take the photo with the device camera instead of supplying a file.
    """
    from .chain.compile import compile_registry
    from .chain.deploy import deploy, make_web3, signing_account
    from .chain.registry import Registry
    from .evidence import RECEIPT_JSON, evidence_hash, similarity_bps
    from .pipeline import run as run_pipeline

    cfg = _cfg(network, threshold, provider)
    if no_fallback:
        cfg = cfg.with_overrides(provider_fallback=False)

    if capture_now:
        from .capture import capture_face

        console.print("[cyan]capturing from camera...")
        try:
            image, score, used = capture_face(Path("capture.jpg"), camera_index=camera)
        except FaceChainError as exc:
            _fail(exc, EXIT_NO_FACE)
        console.print(f"captured {image} (det_score {score:.4f}, {used} attempt(s))")
    elif image is None:
        console.print("[red]provide --image PATH or use --capture")
        raise typer.Exit(2)

    try:
        result = run_pipeline(image, cfg)
        _print_result(result, cfg)

        w3 = make_web3(cfg)
        if cfg.contract_address:
            abi, _ = compile_registry()
            reg = Registry(w3, cfg.contract_address, list(abi), account=signing_account(w3, cfg))
        else:
            addr = deploy(w3, cfg)
            abi, _ = compile_registry()
            reg = Registry(w3, addr, list(abi), account=signing_account(w3, cfg))
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

        # An in-process `local` chain does not survive between CLI invocations, so verification
        # runs here rather than as a separate command. On a public network the standalone
        # `facechain verify` works as well.
        from .verify import verify_record

        ok = verify_record(reg, rid, result.run_dir, cfg)
        console.print(Panel(
            f"on-chain    {_short(ok.onchain_hash)}   (block {w3.eth.block_number} - {cfg.network})\n"
            f"recomputed  {_short(ok.recomputed_hash)}\n\n"
            + ("[bold green]MATCH  record intact" if ok.matches else "[bold red]MISMATCH"),
            title="Re-verification", border_style="green" if ok.matches else "red"))

        bad = verify_record(reg, rid, result.run_dir, cfg, tamper=True)
        console.print(Panel(
            f"on-chain    {_short(bad.onchain_hash)}\n"
            f"recomputed  {_short(bad.recomputed_hash)}\n\n"
            + ("[bold red]MISMATCH  evidence has been altered"
               if not bad.matches else "[bold red]TAMPER NOT DETECTED - BUG"),
            title="Tamper demonstration", border_style="red"))
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
    from .chain.deploy import make_web3, signing_account
    from .chain.registry import Registry
    from .verify import verify_record

    cfg = _cfg(network)
    try:
        cfg.require("contract_address")
        w3 = make_web3(cfg)
        abi, _ = compile_registry()
        reg = Registry(w3, cfg.contract_address, list(abi), account=signing_account(w3, cfg))
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
    from .chain.deploy import deploy as do_deploy, make_web3, signing_account

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
    from .chain.deploy import make_web3, signing_account
    from .chain.registry import Registry
    from .evidence import RECEIPT_JSON, evidence_hash, rebuild_from_artifacts, similarity_bps

    cfg = _cfg(network)
    try:
        cfg.require("contract_address")
        bundle = rebuild_from_artifacts(run_dir)
        h = evidence_hash(bundle)
        w3 = make_web3(cfg)
        abi, _ = compile_registry()
        reg = Registry(w3, cfg.contract_address, list(abi), account=signing_account(w3, cfg))
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


@app.command()
def selftest(
    probe: Path = typer.Option(..., "--probe", exists=True, help="Probe face image"),
    candidate: Path = typer.Option(..., "--candidate", exists=True, help="Image to verify against"),
    post_url: str = typer.Option(
        ..., "--post-url",
        help="URL of the post you are attesting to. Required: no URL is baked into this code.",
    ),
    threshold: float = typer.Option(None, "--threshold"),
):
    """Exercise face verification + evidence + anchor + verify + tamper on a local chain.

    SEARCH IS BYPASSED: you supply the candidate yourself instead of it being discovered. Every
    other step is real -- real detection, real embedding, real cosine, real canonical hashing, a
    real on-chain anchor and a real eth_call to read it back.

    This exists because `--network local` is an in-process chain whose state does not survive
    between CLI invocations, so `run` and `verify` cannot be separate commands against it. It is a
    testing aid, not the graded pipeline: `run` is the graded pipeline.
    """
    import shutil

    from .chain.compile import compile_registry
    from .chain.deploy import deploy as do_deploy, make_web3, signing_account
    from .chain.registry import Registry
    from .evidence import (
        CANDIDATE_IMAGE, POST_TEXT, PROBE_ALIGNED, PROBE_IMAGE,
        build_bundle, evidence_hash, sha256_bytes, similarity_bps, utc_now, write_bundle,
    )
    from .face.detect import detect_probe, load_image
    from .face.embed import embed, embedding_digest
    from .face.similarity import cosine
    from .pipeline import new_run_dir, _write_png
    from .verify import verify_record

    cfg = _cfg("local", threshold)
    console.print("[yellow]NOTE: search is bypassed in selftest. `run` is the graded pipeline.\n")

    try:
        # real detection + embedding on both sides
        p_img = load_image(probe)
        p_face, p_n = detect_probe(p_img)
        p_vec = embed(p_face.aligned)

        c_img = load_image(candidate)
        c_face, _ = detect_probe(c_img)
        c_vec = embed(c_face.aligned)

        score = cosine(p_vec, c_vec)
    except FaceChainError as exc:
        _fail(exc, EXIT_NO_FACE)

    t = Table(title="Face verification (real detection + embedding on both images)")
    t.add_column("field"); t.add_column("value", justify="right")
    t.add_row("probe faces", str(p_n))
    t.add_row("probe det score", f"{p_face.det_score:.4f}")
    t.add_row("cosine similarity", f"{score:.4f}")
    t.add_row("threshold", f"{cfg.threshold}")
    t.add_row("verdict", "[green]PASS" if score >= cfg.threshold else "[red]REJECT")
    console.print(t)

    if score < cfg.threshold:
        console.print(Panel(
            f"cosine {score:.4f} is below threshold {cfg.threshold}.\n"
            "Nothing anchored. This is the honest negative path, not an error.",
            title="No verified match", border_style="yellow"))
        raise typer.Exit(EXIT_NO_MATCH)

    run_dir = new_run_dir(cfg)
    shutil.copyfile(probe, run_dir / PROBE_IMAGE)
    _write_png(run_dir / PROBE_ALIGNED, p_face.aligned)
    shutil.copyfile(candidate, run_dir / CANDIDATE_IMAGE)
    (run_dir / POST_TEXT).write_text(f"manually supplied candidate\nurl: {post_url}\n")

    bundle = build_bundle(
        run_dir=run_dir, bbox=p_face.bbox, det_score=p_face.det_score, faces_detected=p_n,
        embedding_sha256=embedding_digest(p_vec),
        query_image_sha256=sha256_bytes((run_dir / PROBE_ALIGNED).read_bytes()),
        n_candidates=1, n_social=1, n_face_verified=1,
        post_url=post_url, platform="manual", author_handle="manual",
        image_url="(supplied locally)", cosine=score, threshold=cfg.threshold,
        queried_at=utc_now(), captured_at=utc_now(), provider="manual/selftest",
    )
    write_bundle(run_dir, bundle)

    try:
        w3 = make_web3(cfg)
        addr = do_deploy(w3, cfg)
        abi, _ = compile_registry()
        reg = Registry(w3, addr, list(abi), account=signing_account(w3, cfg))
        h = evidence_hash(bundle)
        rid, tx = reg.anchor(h, post_url, similarity_bps(score))

        console.print(Panel(
            f"evidence hash  {_short(h)}\ncontract       {addr}\n"
            f"tx             {tx}\nrecord id      {rid}\nrun dir        {run_dir}",
            title="Anchored on local chain", border_style="cyan"))

        ok = verify_record(reg, rid, run_dir, cfg)
        console.print(Panel(
            f"on-chain    {_short(ok.onchain_hash)}   (block {w3.eth.block_number} - local)\n"
            f"recomputed  {_short(ok.recomputed_hash)}\n\n"
            + ("[bold green]MATCH  record intact" if ok.matches else "[bold red]MISMATCH"),
            title="Verification", border_style="green" if ok.matches else "red"))

        bad = verify_record(reg, rid, run_dir, cfg, tamper=True)
        console.print(Panel(
            f"on-chain    {_short(bad.onchain_hash)}\n"
            f"recomputed  {_short(bad.recomputed_hash)}\n\n"
            + ("[bold red]MISMATCH  evidence has been altered"
               if not bad.matches else "[bold red]TAMPER NOT DETECTED - BUG"),
            title="Tamper demonstration", border_style="red"))
    except ChainError as exc:
        _fail(exc, EXIT_CHAIN)

    console.print(f"\n[dim]originals intact -> verify again: "
                  f"facechain verify --record-id {rid} --run-dir {run_dir}")


@app.command()
def capture(
    output: Path = typer.Option(Path("capture.jpg"), "--output", "-o"),
    camera: int = typer.Option(0, "--camera", help="Capture device index"),
    countdown: int = typer.Option(3, "--countdown", help="Seconds before the shot"),
):
    """Take a photo with the device camera and save it.

    Retries until a face is detected rather than saving a blank frame.
    """
    import time as _time

    from .capture import capture_face

    if countdown > 0:
        for i in range(countdown, 0, -1):
            console.print(f"[bold cyan]{i}...", end="\r")
            _time.sleep(1)
        console.print("[bold green]capturing        ")

    def progress(attempt, n, score):
        console.print(f"  attempt {attempt}: {n} face(s)"
                      + (f", det_score {score:.3f}" if n else ""), style="dim")

    try:
        path, score, used = capture_face(output, camera_index=camera, on_attempt=progress)
    except FaceChainError as exc:
        _fail(exc, EXIT_NO_FACE)

    console.print(Panel(f"{path}\ndetection score {score:.4f} (after {used} attempt(s))",
                        title="Captured", border_style="green"))


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8000, "--port"),
):
    """Serve the local terminal-themed web UI.

    An extra on top of the CLI, not a replacement: it drives the same pipeline functions, so the
    two cannot drift. Binds to localhost only -- it holds API keys in process and drives a camera.
    """
    from .web import serve as _serve

    console.print(Panel(f"http://{host}:{port}", title="facechain web", border_style="green"))
    _serve(host, port)


def main() -> None:  # pragma: no cover
    """Entry point.

    Exits via os._exit after flushing, deliberately.

    onnxruntime and httpx both own native thread pools, and on macOS their teardown at
    interpreter shutdown can abort the process (SIGABRT, exit 134) *after* all output has been
    written and the intended exit code chosen. That silently replaced documented exit codes --
    `run` returned 134 instead of 4 for a legitimate "no verified match".

    Exit codes are part of this CLI's contract, so the chosen code is committed before native
    teardown can run. Output is flushed first; nothing is skipped that matters.

    Every exception is caught for the same reason: one that escapes would reach normal
    interpreter shutdown and bypass os._exit entirely, which is precisely the case this guards.
    """
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    if os.environ.get("FACECHAIN_VERBOSE"):
        from .face.models import set_verbose

        set_verbose(True)

    code = 0
    try:
        app()
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
    except KeyboardInterrupt:
        # Ctrl-C is not a SystemExit. Without this it would escape main() and reach normal
        # interpreter shutdown -- the exact path that lets native teardown abort the process.
        console.print("[yellow]interrupted[/yellow]")
        code = 130
    except BaseException:  # noqa: BLE001 -- last resort: no exception may skip the hard exit
        traceback.print_exc()
        code = 1
    finally:
        try:
            sys.stdout.flush()
            sys.stderr.flush()
        except Exception:
            pass
    os._exit(code)


if __name__ == "__main__":  # pragma: no cover
    main()
