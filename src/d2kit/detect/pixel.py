"""Pixel-based detector: watch a calibrated screen spot for the Accept popup.

Calibration stores fractional screen coordinates plus a target RGB color. Each
poll grabs a frame and, within a ``region`` x ``region`` box around the calibrated
point, counts the fraction of pixels whose color is within ``tolerance`` (RGB
Euclidean distance) of the target. It fires when that fraction reaches
``min_fraction``.

Counting a *region* (rather than averaging a single patch) is what makes this
robust: the popup's pulsing animation, anti-aliased edges, and a slightly-off
calibration click all still leave most of the box filled with the button color,
while a stray same-ish pixel elsewhere can't fake a whole region.
"""

from __future__ import annotations

import numpy as np

from ..capture.base import Frame, ScreenCapturer
from ..config import Calibration
from .base import Detector, MatchEvent


def _region_bounds(h: int, w: int, fx: float, fy: float, size: int) -> tuple[int, int, int, int]:
    cx = min(max(round(fx * w), 0), w - 1)
    cy = min(max(round(fy * h), 0), h - 1)
    r = max(size // 2, 1)
    y0, y1 = max(cy - r, 0), min(cy + r + 1, h)
    x0, x1 = max(cx - r, 0), min(cx + r + 1, w)
    return y0, y1, x0, x1


def patch_mean_rgb(frame: Frame, fx: float, fy: float, patch: int) -> np.ndarray:
    """Mean RGB of an NxN patch centered on fractional coords (fx, fy).

    ``frame`` is BGR uint8 (HxWx3); returns RGB float64 of shape (3,).
    """
    h, w = frame.shape[:2]
    y0, y1, x0, x1 = _region_bounds(h, w, fx, fy, patch)
    region = frame[y0:y1, x0:x1].reshape(-1, frame.shape[2])[:, :3]
    bgr_mean = region.mean(axis=0)
    return bgr_mean[::-1]  # BGR -> RGB


def match_fraction(frame: Frame, calib: Calibration, target: np.ndarray) -> float:
    """Fraction (0..1) of region pixels within ``tolerance`` of ``target`` RGB."""
    h, w = frame.shape[:2]
    y0, y1, x0, x1 = _region_bounds(h, w, calib.x, calib.y, calib.region)
    region = frame[y0:y1, x0:x1, :3].astype(np.float32)
    region_rgb = region[:, :, ::-1]  # BGR -> RGB
    diff = region_rgb - target.astype(np.float32)
    dist = np.sqrt((diff * diff).sum(axis=2))
    return float((dist <= calib.tolerance).mean())


class PixelDetector(Detector):
    def __init__(self, capturer: ScreenCapturer, calib: Calibration) -> None:
        self._cap = capturer
        self._calib = calib
        self._target = np.array(calib.color, dtype=float)

    def preflight(self) -> str | None:
        if not self._calib.calibrated:
            return "Not calibrated yet. Run  d2kit --config  first."
        return None

    def start(self) -> None:
        self._cap.start()

    def measure(self) -> float:
        """Current match fraction at the calibrated spot (for tuning/debug)."""
        return match_fraction(self._cap.grab(), self._calib, self._target)

    def poll(self) -> MatchEvent | None:
        frac = match_fraction(self._cap.grab(), self._calib, self._target)
        if frac >= self._calib.min_fraction:
            return MatchEvent(confidence=frac)
        return None

    def stop(self) -> None:
        self._cap.stop()
