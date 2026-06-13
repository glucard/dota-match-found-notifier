"""Capture backends plus the auto-selecting factory.

Selection rule:
  * Windows                -> mss
  * Linux + X11 session    -> mss
  * Linux + Wayland        -> PipeWire portal
A backend can be forced via config (``capture.backend`` = "mss" | "pipewire");
"auto" applies the rule above. Unavailable forced backends fail loudly.
"""

from __future__ import annotations

import os
import sys

from ..config import CaptureConfig
from .base import CaptureError, Frame, ScreenCapturer
from .mss_backend import MssCapturer
from .pipewire_backend import PipewireCapturer

__all__ = [
    "CaptureError",
    "Frame",
    "MssCapturer",
    "PipewireCapturer",
    "ScreenCapturer",
    "is_wayland",
    "make_capturer",
]


def is_wayland() -> bool:
    """True if the current Linux session is Wayland."""
    if sys.platform != "linux":
        return False
    if os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland":
        return True
    return bool(os.environ.get("WAYLAND_DISPLAY"))


def make_capturer(cfg: CaptureConfig) -> ScreenCapturer:
    backend = (cfg.backend or "auto").lower()

    if backend == "mss":
        return MssCapturer()
    if backend == "pipewire":
        return PipewireCapturer(cfg.restore_token)
    if backend != "auto":
        raise CaptureError(f"Unknown capture backend: {cfg.backend!r}")

    # auto
    if is_wayland():
        return PipewireCapturer(cfg.restore_token)
    return MssCapturer()
