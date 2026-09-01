"""Webcam capture -- the literal "face scan" input.

Kept separate from `face.detect` because this is an I/O device concern, not image analysis. The
only thing it produces is a JPEG on disk; everything downstream treats it like any other input.

macOS requires camera permission for the process that opens the device. The first attempt
triggers a system prompt; if the process was launched somewhere that cannot show one, the open
fails and we say so plainly rather than hanging.
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np

from .errors import FaceChainError

WARMUP_FRAMES = 15  # cameras need a moment for auto-exposure and white balance to settle


def open_camera(index: int = 0):
    """Open a capture device, preferring AVFoundation on macOS."""
    import cv2

    backends = [getattr(cv2, "CAP_AVFOUNDATION", None), getattr(cv2, "CAP_ANY", None)]
    for backend in [b for b in backends if b is not None]:
        cam = cv2.VideoCapture(index, backend)
        if cam.isOpened():
            return cam
        cam.release()

    raise FaceChainError(
        "could not open the camera",
        {
            "index": index,
            "hint": "grant Camera permission to your terminal in "
                    "System Settings > Privacy & Security > Camera, then retry",
        },
    )


def grab_frame(cam, warmup: int = WARMUP_FRAMES) -> np.ndarray:
    """Read a settled frame, discarding the first few while exposure stabilises."""
    frame = None
    for _ in range(max(1, warmup)):
        ok, f = cam.read()
        if ok and f is not None:
            frame = f
        time.sleep(0.03)
    if frame is None:
        raise FaceChainError("camera opened but returned no frame")
    return frame


def capture_face(
    output: Path,
    camera_index: int = 0,
    attempts: int = 12,
    require_face: bool = True,
    on_attempt=None,
) -> tuple[Path, float, int]:
    """Capture until a face is detected. Returns (path, det_score, attempts_used).

    Retries rather than saving a faceless frame: a blank capture would fail later anyway, and
    failing at the camera is a far clearer error than failing three stages downstream.
    """
    import cv2

    from .face.detect import detect_faces

    cam = open_camera(camera_index)
    try:
        best_frame, best_score, used = None, 0.0, 0
        for attempt in range(1, attempts + 1):
            used = attempt
            frame = grab_frame(cam, WARMUP_FRAMES if attempt == 1 else 3)
            if not require_face:
                best_frame, best_score = frame, 0.0
                break

            faces = detect_faces(frame)
            if on_attempt:
                on_attempt(attempt, len(faces), faces[0].det_score if faces else 0.0)
            if faces:
                best_frame, best_score = frame, faces[0].det_score
                break
            time.sleep(0.25)

        if best_frame is None:
            raise FaceChainError(
                "no face detected from the camera",
                {"attempts": used, "hint": "face the camera, check lighting, and retry"},
            )

        output.parent.mkdir(parents=True, exist_ok=True)
        if not cv2.imwrite(str(output), best_frame):
            raise FaceChainError("could not write captured image", {"path": str(output)})
        return output, best_score, used
    finally:
        cam.release()
