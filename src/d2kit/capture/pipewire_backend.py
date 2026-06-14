"""PipeWire ScreenCast capture for GNOME Wayland (and other Wayland sessions).

On GNOME Wayland the X11 root grab (mss) returns black for fullscreen XWayland
games, so we capture through the ``xdg-desktop-portal`` ScreenCast interface via
the ``pipewire-capture`` library.

Flow (per the library): ``PortalCapture.select_window()`` shows the system
"share your screen" picker once and returns a ``PortalSession``; we open a
``CaptureStream`` on it and poll ``get_frame()`` (BGRA) for the lifetime of the
process. One session is held for the whole run, so the picker appears once per
launch.

Note: this library version exposes no restore-token, so consent cannot persist
across separate launches yet. ``restore_token`` is accepted for forward-compat
but currently unused.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import numpy as np

from .base import CaptureError, Frame

log = logging.getLogger(__name__)

_FIRST_FRAME_TIMEOUT = 5.0  # seconds to wait for the first PipeWire frame
_CAPTURE_INTERVAL = 0.1  # native capture cadence; faster than the default 0.25s


class PipewireCapturer:
    def __init__(self, restore_token: str = "") -> None:
        self._restore_token = restore_token  # reserved; not used by this lib version
        self._portal: Any = None  # pipewire_capture objects; the lib is untyped
        self._session: Any = None
        self._stream: Any = None
        self._last: Frame | None = None
        self._size = (0, 0)

    def start(self) -> None:
        import pipewire_capture as pw

        if not pw.is_available():
            raise CaptureError(
                "PipeWire screen-capture portal is unavailable. Ensure "
                "xdg-desktop-portal and a portal backend (e.g. "
                "xdg-desktop-portal-gnome) plus PipeWire are running."
            )
        self._portal = pw.PortalCapture()
        session = self._portal.select_window()  # blocking picker dialog
        if session is None:
            raise CaptureError("Screen-share was cancelled in the portal dialog.")
        self._session = session
        self._size = (session.width, session.height)
        self._stream = pw.CaptureStream(
            session.fd,
            session.node_id,
            session.width,
            session.height,
            capture_interval=_CAPTURE_INTERVAL,
        )
        self._stream.start()
        self._await_first_frame()

    def _await_first_frame(self) -> None:
        deadline = time.monotonic() + _FIRST_FRAME_TIMEOUT
        while time.monotonic() < deadline:
            frame = self._stream.get_frame()
            if frame is not None:
                self._last = self._to_bgr(frame)
                return
            time.sleep(0.05)
        raise CaptureError(
            "No frame received from PipeWire within "
            f"{_FIRST_FRAME_TIMEOUT:.0f}s of starting capture."
        )

    @staticmethod
    def _to_bgr(frame: np.ndarray) -> Frame:
        # Library returns (H, W, 4) BGRA; drop alpha -> BGR uint8.
        return np.asarray(frame, dtype=np.uint8)[:, :, :3]

    def grab(self) -> Frame:
        if self._stream is None:
            raise CaptureError("PipewireCapturer.grab() called before start()")
        frame = self._stream.get_frame()
        if frame is not None:
            self._last = self._to_bgr(frame)
        if self._last is None:
            raise CaptureError("No PipeWire frame available yet.")
        return self._last

    def stop(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream = None
        if self._session is not None:
            self._session.close()
            self._session = None
        self._portal = None

    @property
    def size(self) -> tuple[int, int]:
        return self._size
