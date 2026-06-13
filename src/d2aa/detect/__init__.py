"""Detector backends plus the config-driven factory."""

from __future__ import annotations

from ..capture.base import ScreenCapturer
from ..config import Config
from .base import Detector, MatchEvent
from .pixel import PixelDetector

__all__ = ["Detector", "MatchEvent", "PixelDetector", "make_detector"]


def make_detector(cfg: Config, capturer: ScreenCapturer) -> Detector:
    backend = cfg.detector.backend.lower()
    if backend == "pixel":
        return PixelDetector(capturer, cfg.calibration)
    if backend == "netcon":
        # Reserved for the Linux-only -netconport detector (see plan).
        raise NotImplementedError("The 'netcon' detector is not implemented yet; use 'pixel'.")
    raise ValueError(f"Unknown detector backend: {cfg.detector.backend!r}")
