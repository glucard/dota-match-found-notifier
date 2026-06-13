"""mss-based capture for Windows and Linux/X11.

Grabs the full virtual screen (the union of all monitors, ``monitors[0]``). Note:
on a GNOME *Wayland* session this captures the X11 root, which excludes native
Wayland and fullscreen XWayland surfaces (it comes back black) — the factory
routes Wayland to the PipeWire backend instead.
"""

from __future__ import annotations

import numpy as np

from .base import CaptureError, Frame


class MssCapturer:
    def __init__(self) -> None:
        self._sct = None
        self._monitor = None
        self._size = (0, 0)

    def start(self) -> None:
        import mss  # imported lazily so the import cost/error is scoped here

        self._sct = mss.mss()
        # monitors[0] is the full virtual screen across all displays.
        self._monitor = self._sct.monitors[0]
        self._size = (self._monitor["width"], self._monitor["height"])

    def grab(self) -> Frame:
        if self._sct is None:
            raise CaptureError("MssCapturer.grab() called before start()")
        shot = self._sct.grab(self._monitor)
        # mss returns BGRA; drop alpha to BGR uint8.
        arr = np.asarray(shot, dtype=np.uint8)[:, :, :3]
        return arr

    def stop(self) -> None:
        if self._sct is not None:
            self._sct.close()
            self._sct = None

    @property
    def size(self) -> tuple[int, int]:
        return self._size
