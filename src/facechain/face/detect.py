"""Face detection and alignment (SCRFD via InsightFace).

Detections are returned sorted by det_score descending, so index 0 is always the probe (FR-003).
Zero detections raises rather than fabricating anything (FR-005).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ..errors import FaceChainError, NoFaceDetectedError

MAX_PIXELS = 50_000_000  # reject absurd images before decode (NFR-012)


@dataclass(frozen=True)
class DetectedFace:
    bbox: tuple[int, int, int, int]  # x, y, w, h
    landmarks: np.ndarray  # (5, 2) float32
    det_score: float
    aligned: np.ndarray  # (112, 112, 3) uint8

    @property
    def area(self) -> int:
        return self.bbox[2] * self.bbox[3]


def load_image(path: Path) -> np.ndarray:
    """Decode an image from disk as BGR."""
    import cv2

    p = Path(path)
    if not p.exists():
        raise FaceChainError("image not found", {"path": str(p)})
    if p.stat().st_size == 0:
        raise FaceChainError("image file is empty", {"path": str(p)})

    img = cv2.imread(str(p), cv2.IMREAD_COLOR)
    if img is None:
        raise FaceChainError("could not decode image", {"path": str(p)})
    if img.shape[0] * img.shape[1] > MAX_PIXELS:
        raise FaceChainError("image too large", {"path": str(p), "shape": str(img.shape)})
    return img


def detect_faces(image: np.ndarray) -> list[DetectedFace]:
    """Detect faces, highest det_score first.

    Returns [] for an image with no faces; callers that require a probe raise NoFaceDetectedError.
    """
    from .models import get_app

    faces = get_app().get(image)
    out: list[DetectedFace] = []
    for f in faces:
        x1, y1, x2, y2 = (int(v) for v in f.bbox)
        aligned = _align(image, f)
        out.append(
            DetectedFace(
                bbox=(x1, y1, max(0, x2 - x1), max(0, y2 - y1)),
                landmarks=np.asarray(f.kps, dtype=np.float32),
                det_score=float(f.det_score),
                aligned=aligned,
            )
        )
    out.sort(key=lambda d: d.det_score, reverse=True)
    return out


def detect_probe(image: np.ndarray) -> tuple[DetectedFace, int]:
    """Return (probe, total_faces_detected). Raises when there is no face."""
    faces = detect_faces(image)
    if not faces:
        raise NoFaceDetectedError("no face detected in image")
    return faces[0], len(faces)


def _align(image: np.ndarray, face) -> np.ndarray:
    """Landmark-based alignment to a deterministic 112x112 crop.

    Determinism matters: the aligned crop is hashed into the evidence chain, so the same input
    must always produce byte-identical output.
    """
    from insightface.utils import face_align

    return face_align.norm_crop(image, landmark=face.kps, image_size=112)
