"""Head crop with the background and clothing removed, used as the SEARCH QUERY.

Why this exists: a real run against a photo of a person in a red kurta returned 60 Google Lens
results, essentially all of them garment listings -- eBay, Etsy, Manyavar, KALKI. Lens decided the
salient subject was the clothing and never tried to match the face. Removing everything but the
head takes that option away from the matcher.

Two separate images now come out of one detection, and conflating them would be a mistake:

  probe_aligned.png  112x112, ArcFace alignment  -> the EMBEDDING. Never changed; the whole
                                                    evidence chain and every threshold depends on
                                                    it staying byte-identical.
  probe_head.png     square, background removed  -> the SEARCH QUERY. Larger, because a 112px
                                                    thumbnail gives a reverse-image engine almost
                                                    nothing to work with.
"""

from __future__ import annotations

import numpy as np

DEFAULT_SIZE = 512
# Neutral mid-grey. Not white: white backgrounds bias product search engines toward catalogue
# and stock imagery, which is the failure mode this module exists to avoid.
BACKGROUND = (128, 128, 128)


def head_region(bbox: tuple[int, int, int, int], shape: tuple[int, ...]) -> tuple[int, int, int, int]:
    """Expand a face bbox to cover the whole head, clamped to the image.

    The detector's box covers the face only. Hair and the top of the skull sit above it, and both
    carry identity information a reverse-image search can use, so the box is grown more upward
    than downward -- growing downward mostly adds shoulders and collar, which is exactly the
    clothing we are trying to exclude.
    """
    x, y, w, h = bbox
    up, side, down = 0.55, 0.30, 0.18
    x0 = int(round(x - w * side))
    x1 = int(round(x + w * (1 + side)))
    y0 = int(round(y - h * up))
    y1 = int(round(y + h * (1 + down)))

    H, W = shape[0], shape[1]
    return max(0, x0), max(0, y0), min(W, x1), min(H, y1)


def _elliptical_mask(h: int, w: int, feather: int = 0) -> np.ndarray:
    """A soft-edged ellipse filling the crop, as a float mask in [0, 1]."""
    import cv2

    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.ellipse(
        mask,
        center=(w // 2, int(h * 0.52)),
        axes=(int(w * 0.46), int(h * 0.48)),
        angle=0, startAngle=0, endAngle=360, color=255, thickness=-1,
    )
    if feather <= 0:
        feather = max(3, (min(h, w) // 12) | 1)  # odd kernel
    mask = cv2.GaussianBlur(mask, (feather, feather), 0)
    return (mask.astype(np.float32) / 255.0)[..., None]


def head_crop(
    image: np.ndarray,
    bbox: tuple[int, int, int, int],
    size: int = DEFAULT_SIZE,
    remove_background: bool = True,
) -> np.ndarray:
    """Return a square head crop, optionally composited onto a neutral background."""
    import cv2

    x0, y0, x1, y1 = head_region(bbox, image.shape)
    if x1 <= x0 or y1 <= y0:
        raise ValueError("degenerate head region")

    crop = image[y0:y1, x0:x1]

    # Pad to square before resizing so the face is not stretched.
    h, w = crop.shape[:2]
    side = max(h, w)
    top, left = (side - h) // 2, (side - w) // 2
    square = cv2.copyMakeBorder(
        crop, top, side - h - top, left, side - w - left,
        cv2.BORDER_CONSTANT, value=BACKGROUND,
    )
    out = cv2.resize(square, (size, size), interpolation=cv2.INTER_CUBIC)

    if remove_background:
        mask = _elliptical_mask(size, size)
        bg = np.full_like(out, BACKGROUND, dtype=np.uint8)
        out = (out.astype(np.float32) * mask + bg.astype(np.float32) * (1.0 - mask))
        out = np.clip(out, 0, 255).astype(np.uint8)

    return out
