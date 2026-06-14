from __future__ import annotations

import numpy as np

from d2kit.config import Calibration
from d2kit.detect.pixel import PixelDetector, patch_mean_rgb


class FakeCapturer:
    """In-memory capturer returning a fixed BGR frame."""

    def __init__(self, frame: np.ndarray) -> None:
        self._frame = frame
        self.started = False

    def start(self) -> None:
        self.started = True

    def grab(self) -> np.ndarray:
        return self._frame

    def stop(self) -> None:
        self.started = False

    @property
    def size(self) -> tuple[int, int]:
        h, w = self._frame.shape[:2]
        return w, h


def _solid_bgr(h: int, w: int, rgb: tuple[int, int, int]) -> np.ndarray:
    r, g, b = rgb
    frame = np.zeros((h, w, 3), np.uint8)
    frame[:, :, 0] = b
    frame[:, :, 1] = g
    frame[:, :, 2] = r
    return frame


def test_patch_mean_rgb_reads_rgb_from_bgr():
    frame = _solid_bgr(50, 80, (243, 145, 38))
    mean = patch_mean_rgb(frame, 0.5, 0.5, 5)
    assert list(np.round(mean)) == [243, 145, 38]


def test_detects_matching_color():
    frame = _solid_bgr(100, 100, (243, 145, 38))
    calib = Calibration(x=0.5, y=0.5, color=[243, 145, 38], tolerance=40)
    det = PixelDetector(FakeCapturer(frame), calib)
    det.start()
    event = det.poll()
    assert event is not None
    assert event.kind == "match_found"
    assert 0.0 <= event.confidence <= 1.0


def test_ignores_offcolor():
    frame = _solid_bgr(100, 100, (10, 10, 10))  # black-ish, not the popup
    calib = Calibration(x=0.5, y=0.5, color=[243, 145, 38], tolerance=40)
    det = PixelDetector(FakeCapturer(frame), calib)
    det.start()
    assert det.poll() is None


def test_tolerance_boundary():
    # target 100,100,100; frame 100,100,130 -> distance 30
    frame = _solid_bgr(20, 20, (100, 100, 130))
    inside = PixelDetector(FakeCapturer(frame), Calibration(color=[100, 100, 100], tolerance=31))
    outside = PixelDetector(FakeCapturer(frame), Calibration(color=[100, 100, 100], tolerance=29))
    assert inside.poll() is not None
    assert outside.poll() is None


def test_fractional_coords_survive_resolution():
    # Same fractional point on two resolutions lands on the orange block. The
    # block is painted larger than the detection region so the match fraction
    # is high regardless of resolution.
    for h, w in [(200, 200), (1080, 1920)]:
        frame = np.zeros((h, w, 3), np.uint8)
        y, x = int(0.8 * h), int(0.8 * w)
        frame[y - 20 : y + 21, x - 20 : x + 21] = (38, 145, 243)  # BGR orange
        det = PixelDetector(
            FakeCapturer(frame), Calibration(x=0.8, y=0.8, color=[243, 145, 38], tolerance=30)
        )
        assert det.poll() is not None


def test_partial_region_below_min_fraction():
    # A tiny patch of target color shouldn't trip detection when most of the
    # region is off-color (guards against single-pixel false positives).
    frame = _solid_bgr(200, 200, (10, 10, 10))
    y = x = 160  # 0.8 * 200
    frame[y, x] = (38, 145, 243)  # a single orange pixel
    det = PixelDetector(
        FakeCapturer(frame),
        Calibration(x=0.8, y=0.8, color=[243, 145, 38], tolerance=30, min_fraction=0.25),
    )
    assert det.poll() is None
