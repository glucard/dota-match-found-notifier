"""Screen-capture abstraction.

A backend grabs the full virtual screen as a BGR ``uint8`` numpy array. The rest
of the app only ever touches this interface, so swapping mss <-> PipeWire (or
adding a new backend) never reaches the detector or app loop.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np

# HxWx3 uint8, channel order BGR. Backends normalize to this.
Frame = np.ndarray


class CaptureError(Exception):
    """Raised when a backend cannot produce a usable frame."""


@runtime_checkable
class ScreenCapturer(Protocol):
    def start(self) -> None:
        """Acquire resources (portal session, X connection, ...)."""

    def grab(self) -> Frame:
        """Return the latest full-screen frame as BGR uint8 (HxWx3)."""

    def stop(self) -> None:
        """Release resources. Safe to call more than once."""

    @property
    def size(self) -> tuple[int, int]:
        """Captured frame size as ``(width, height)`` in pixels."""
