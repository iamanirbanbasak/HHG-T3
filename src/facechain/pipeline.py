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
from dataclasses import dataclass, field
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
from .profiles import Account, group_accounts, handle_of, platform_of
from .search.candidates import filter_social, normalise_url, registrable_host, union
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
    # Social/profile URLs published on the face-verified page. Not independently scored.
    linked: list[Account] = field(default_factory=list)
    # Same-handle profiles on other platforms that independently cleared tau.
    expanded: list[ScoredCandidate] = field(default_factory=list)
    resolved_handle: str | None = None
    resolved_profile: str | None = None


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
    from .search.permalink import resolve_owner

    owner = resolve_owner(top.candidate, providers.fetch_page, cfg)
    profile = Account(platform=platform_of(top.candidate.page_url), handle=owner).profile_url if owner else None
    linked = _linked_from_verified_page(top, survivors, cfg, providers)
    expanded = _expand_same_handle(probe_vec, top, survivors, run_dir, cfg, providers, handle=owner)
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
        n_verified=len(survivors), scored=scored, linked=linked, expanded=expanded,
        resolved_handle=owner, resolved_profile=profile,
    )


def _linked_from_verified_page(
    top: ScoredCandidate,
    survivors: list[ScoredCandidate],
    cfg: Config,
    providers: Providers,
) -> list[Account]:
    """Read socials published on the face-verified page, including one link-in-bio hop.

    Instagram's public HTML usually contains none of these -- unlike a Devfolio page --
    so this often returns nothing for an Instagram match. Same-handle expansion is a
    separate step and still has to pass the embedding.
    """
    if providers.fetch_page is None:
        return []

    from .search.page_links import extract_hub_links, extract_profile_links

    page = top.candidate.page_url
    try:
        html = providers.fetch_page(page, cfg)
    except Exception as exc:  # noqa: BLE001 - enrichment must not abort a verified run
        log.warning("could not read verified page for linked profiles: %s", exc)
        return []

    urls = extract_profile_links(html, page, cfg)
    for hub in extract_hub_links(html, page):
        try:
            hub_html = providers.fetch_page(hub, cfg)
        except Exception as exc:  # noqa: BLE001
            log.warning("could not read link-in-bio page: %s", exc)
            continue
        urls.extend(extract_profile_links(hub_html, hub, cfg))

    known = {normalise_url(s.candidate.page_url) for s in survivors}
    urls = [u for u in urls if normalise_url(u) not in known]
    if not urls:
        return []

    accounts = group_accounts([(u, 0.0) for u in urls])
    for a in accounts:
        a.origin = "linked"
    return accounts


def _expand_same_handle(
    probe_vec,
    top: ScoredCandidate,
    survivors: list[ScoredCandidate],
    run_dir: Path,
    cfg: Config,
    providers: Providers,
    handle: str | None = None,
) -> list[ScoredCandidate]:
    """If a verified profile carries a handle, try that handle on other platforms.

    Instagram post permalinks do not include a handle. `handle` must already have been
    resolved from provider text, oEmbed, or the page -- never invented from the shortcode.
    """
    handle = handle or handle_of(top.candidate.page_url)
    if not handle:
        return []

    from .search.lens import Candidate
    from .search.page_links import og_image, profile_guesses

    known = {normalise_url(s.candidate.page_url) for s in survivors}
    cands: list[Candidate] = []
    for platform, page, avatar in profile_guesses(handle, platform_of(top.candidate.page_url)):
        if normalise_url(page) in known:
            continue
        image_url = avatar
        if not image_url:
            if providers.fetch_page is None:
                continue
            try:
                html = providers.fetch_page(page, cfg)
            except Exception as exc:  # noqa: BLE001
                log.info("same-handle %s unreachable: %s", page, exc)
                continue
            image_url = og_image(html, page)
        if not image_url:
            continue
        cands.append(Candidate(
            page_url=page, image_url=image_url, title=platform, source="handle",
        ))
        known.add(normalise_url(page))

    if providers.web_search is not None:
        try:
            found = providers.web_search(handle, cfg) or []
        except Exception as exc:  # noqa: BLE001 - enrichment must not abort a verified run
            log.warning("linkedin search failed: %s", exc)
            found = []
        for c in found:
            if normalise_url(c.page_url) in known:
                continue
            image_url = c.image_url
            if not image_url and providers.fetch_page is not None:
                try:
                    image_url = og_image(providers.fetch_page(c.page_url, cfg), c.page_url)
                except Exception:  # noqa: BLE001
                    image_url = ""
            if not image_url:
                continue
            cands.append(Candidate(
                page_url=c.page_url, image_url=image_url,
                title=c.title, source="linkedin-search",
                thumbnail_url=c.thumbnail_url,
            ))
            known.add(normalise_url(c.page_url))

    if not cands:
        return []

    scored = verify_candidates(probe_vec, cands, run_dir / "handle-expand", cfg, providers)
    admitted = [s for s in scored if s.cosine >= cfg.threshold]
    for s in scored:
        log.info(
            "same-handle %s cosine %.4f %s",
            s.candidate.page_url, s.cosine,
            "PASS" if s.cosine >= cfg.threshold else "reject",
        )
    return admitted


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
