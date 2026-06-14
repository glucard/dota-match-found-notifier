"""Detector backends plus the config-driven factory."""

from __future__ import annotations

from ..capture.base import ScreenCapturer
from ..config import Config
from .base import Detector, MatchEvent
from .console import ConsoleLogDetector
from .pixel import PixelDetector

__all__ = [
    "ConsoleLogDetector",
    "Detector",
    "MatchEvent",
    "PixelDetector",
    "make_detector",
]


def make_detector(cfg: Config, capturer: ScreenCapturer | None = None) -> Detector:
    """Build the configured detector. Only the pixel backend needs a capturer."""
    backend = cfg.detector.backend.lower()
    if backend == "pixel":
        if capturer is None:
            raise ValueError("The pixel detector requires a screen capturer.")
        return PixelDetector(capturer, cfg.calibration)
    if backend == "console":
        return ConsoleLogDetector(cfg.detector.console.log_path, cfg.detector.console.triggers)
    raise ValueError(f"Unknown detector backend: {cfg.detector.backend!r}")
