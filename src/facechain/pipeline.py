"""The end-to-end pipeline: detect, embed, search, verify candidates, build evidence.

The design decision this module exists to enforce (spec section 2):

    The reverse-image query is the ALIGNED FACE CROP, and every candidate returned is
    INDEPENDENTLY re-detected and re-embedded and scored against the probe.

Without the second half, the face embedding is decorative and the project is an image lookup
wearing a face-recognition costume. `verify_candidates` is what makes it load-bearing, and it is
the first function an adversarial reviewer should read.
"""

from __future__ import annotations

import logging
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .config import Config
from .errors import CandidateFetchError, NoVerifiedMatchError
from .evidence import (
    CANDIDATE_IMAGE,
    POST_TEXT,
    PROBE_ALIGNED,
    PROBE_HEAD,
    PROBE_IMAGE,
    build_bundle,
    sha256_bytes,
    utc_now,
    write_bundle,
)
from .face.detect import detect_probe, load_image
from .face.embed import embed, embedding_digest
from .face.similarity import cosine
from .providers import Providers, default_providers
from .search.candidates import filter_social, registrable_host, union
from .search.lens import Candidate

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScoredCandidate:
    candidate: Candidate
    cosine: float
    image_path: Path


@dataclass
class RunResult:
    run_dir: Path
    bundle: dict
    top: ScoredCandidate
    n_candidates: int
    n_social: int
    n_verified: int
    scored: list[ScoredCandidate]


def new_run_dir(cfg: Config) -> Path:
    d = Path(cfg.artifacts_dir) / f"run-{uuid.uuid4().hex[:12]}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def verify_candidates(
    probe_vec: np.ndarray,
    candidates: list[Candidate],
    run_dir: Path,
    cfg: Config,
    providers: Providers,
) -> list[ScoredCandidate]:
    """Independently detect + embed + score every candidate. THIS is the load-bearing step.

    A candidate whose image contains no face is skipped, not scored zero: "no face" and "poor
    match" are different outcomes, and scoring it zero would pollute the calibration distributions.
    """
    scored: list[ScoredCandidate] = []
    seen_images: dict[str, float] = {}  # in-run cache; never embed the same image twice
    workdir = run_dir / "candidates"
    workdir.mkdir(parents=True, exist_ok=True)

    for i, cand in enumerate(candidates):
        if not cand.image_url and not cand.image_b64:
            continue
        try:
            key = cand.page_url if cand.image_b64 else cand.image_url
            if key in seen_images:
                score = seen_images[key]
                path = workdir / f"c{i:03d}.jpg"
            else:
                path = _materialise(cand, workdir / f"c{i:03d}.jpg", cfg, providers)
                img = load_image(path)
                faces = _detect_or_none(img)
                if faces is None:
                    log.info("candidate %s has no detectable face, skipping", cand.page_url)
                    continue
                score = cosine(probe_vec, embed(faces.aligned))
                seen_images[key] = score
        except CandidateFetchError as exc:
            # One candidate failing is not a failed run.
            log.warning("skipping candidate: %s", exc)
            continue
        except Exception as exc:  # noqa: BLE001 - a malformed candidate must not abort the run
            log.warning("skipping unreadable candidate %s: %s", cand.page_url, exc)
            continue

        scored.append(ScoredCandidate(candidate=cand, cosine=score, image_path=path))

    scored.sort(key=lambda s: s.cosine, reverse=True)
    return scored


def _materialise(cand: Candidate, dest: Path, cfg: Config, providers: Providers) -> Path:
    """Get the candidate's image onto disk.

    Providers that return an inline thumbnail need no outbound request at all, which sidesteps
    the hotlink 403s that social CDNs routinely serve.
    """
    if cand.image_b64:
        import base64
        import binascii

        raw = cand.image_b64
        if "," in raw[:64]:  # strip a data: URI prefix if present
            raw = raw.split(",", 1)[1]
        try:
            data = base64.b64decode(raw, validate=False)
        except (binascii.Error, ValueError) as exc:
            raise CandidateFetchError("inline thumbnail is not valid base64") from exc
        if not data:
            raise CandidateFetchError("inline thumbnail is empty")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return dest

    try:
        return providers.fetch_image(cand.image_url, dest, cfg)
    except CandidateFetchError:
        # Social CDNs frequently refuse hotlinked full-size images. Rather than lose the
        # candidate entirely, retry the lower-resolution thumbnail.
        if cand.thumbnail_url and cand.thumbnail_url != cand.image_url:
            log.info("full-size fetch failed, falling back to thumbnail for %s", cand.page_url)
            return providers.fetch_image(cand.thumbnail_url, dest, cfg)
        raise


def _detect_or_none(img: np.ndarray):
    from .errors import NoFaceDetectedError

    try:
        face, _ = detect_probe(img)
        return face
    except NoFaceDetectedError:
        return None


def run(
    image: Path,
    cfg: Config,
    providers: Providers | None = None,
    post_text_for: "callable | None" = None,
) -> RunResult:
    """Execute stages 1-5 and return the evidence bundle.

    Raises NoVerifiedMatchError when no candidate clears the threshold. The pipeline never
    fabricates a match, never lowers the threshold, and never falls back to a best-available
    candidate below tau.
    """
    providers = providers or default_providers(cfg)
    run_dir = new_run_dir(cfg)
    queried_at = utc_now()

    # 1-2. detect + embed the probe
    img = load_image(Path(image))
    probe, faces_detected = detect_probe(img)
    probe_vec = embed(probe.aligned)

    shutil.copyfile(image, run_dir / PROBE_IMAGE)
    _write_png(run_dir / PROBE_ALIGNED, probe.aligned)

    # The search query is a large head crop with background and clothing masked out. Sending the
    # 112x112 ArcFace crop instead gave reverse-image search almost nothing to work with, and
    # sending the full photo let it match the subject's clothing rather than their face -- one
    # real run returned 60 results that were almost entirely garment listings.
    from .face.headcrop import head_crop

    try:
        _write_png(run_dir / PROBE_HEAD, head_crop(img, probe.bbox))
        query_image = run_dir / PROBE_HEAD
    except Exception as exc:  # noqa: BLE001 - never lose a run over a crop failure
        log.warning("head crop failed, falling back to the aligned crop: %s", exc)
        query_image = run_dir / PROBE_ALIGNED

    # 3. search: the ALIGNED CROP is the primary query; the full photo widens recall only.
    # The provider decides how the image reaches the service (public host vs direct upload).
    crop_hits = providers.face_search(query_image, cfg)
    photo_hits = providers.face_search(run_dir / PROBE_IMAGE, cfg)

    all_cands = union(crop_hits, photo_hits)
    social = filter_social(all_cands, cfg)

    # 4. independent face verification of every candidate
    scored = verify_candidates(probe_vec, social, run_dir, cfg, providers)
    survivors = [s for s in scored if s.cosine >= cfg.threshold]

    if not survivors:
        raise NoVerifiedMatchError(
            "no candidate cleared the similarity threshold",
            {
                "candidates": len(all_cands),
                "social": len(social),
                "scored": len(scored),
                "threshold": cfg.threshold,
                "best": round(max((s.cosine for s in scored), default=0.0), 4),
            },
        )

    top = survivors[0]
    shutil.copyfile(top.image_path, run_dir / CANDIDATE_IMAGE)

    text = post_text_for(top.candidate) if post_text_for else _post_text(top.candidate)
    (run_dir / POST_TEXT).write_text(text, encoding="utf-8")

    bundle = build_bundle(
        run_dir=run_dir,
        bbox=probe.bbox,
        det_score=probe.det_score,
        faces_detected=faces_detected,
        embedding_sha256=embedding_digest(probe_vec),
        query_image_sha256=sha256_bytes(query_image.read_bytes()),
        n_candidates=len(all_cands),
        n_social=len(social),
        n_face_verified=len(survivors),
        post_url=top.candidate.page_url,
        platform=registrable_host(top.candidate.page_url),
        author_handle=_handle(top.candidate.page_url),
        image_url=top.candidate.image_url,
        cosine=top.cosine,
        threshold=cfg.threshold,
        queried_at=queried_at,
        captured_at=utc_now(),
    )
    write_bundle(run_dir, bundle)

    return RunResult(
        run_dir=run_dir, bundle=bundle, top=top,
        n_candidates=len(all_cands), n_social=len(social),
        n_verified=len(survivors), scored=scored,
    )


def _post_text(cand: Candidate) -> str:
    """Text associated with the matched post.

    AMB-06: Lens returns a page URL, a title, and a source rather than full post text. This
    records what the provider actually returned, labelled as such -- it is not scraped post body
    text, and the README says so.
    """
    return (
        f"source: {cand.source}\n"
        f"title: {cand.title}\n"
        f"url: {cand.page_url}\n"
    )


def _handle(url: str) -> str:
    parts = [p for p in url.split("/") if p]
    for p in parts:
        if p.startswith("@"):
            return p
    return parts[2] if len(parts) > 2 else ""


def _write_png(path: Path, arr: np.ndarray) -> None:
    import cv2

    cv2.imwrite(str(path), arr)
