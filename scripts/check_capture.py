"""Acceptance-gate check: prove the configured capture backend returns a real
(non-black) frame. Saves a PNG and prints basic stats.

Usage:  uv run python scripts/check_capture.py [out.png]
"""

from __future__ import annotations

import sys

import numpy as np
from PIL import Image

from d2kit.capture import make_capturer
from d2kit.config import CaptureConfig


def main() -> int:
    out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/d2kit_capture_check.png"
    cap = make_capturer(CaptureConfig(backend="auto"))
    print(f"backend: {type(cap).__name__}")
    print("If a screen-share picker appears, choose 'Entire Screen' and Share.")
    cap.start()
    try:
        frame = cap.grab()  # BGR uint8 (H, W, 3)
    finally:
        # keep one more grab to be safe, then stop
        cap.stop()

    h, w = frame.shape[:2]
    mean = float(frame.mean())
    std = float(frame.std())
    nonzero = float((frame.any(axis=2)).mean()) * 100.0
    print(f"size: {w}x{h}  mean={mean:.1f}  std={std:.1f}  non-black-pixels={nonzero:.1f}%")

    # Save RGB PNG (frame is BGR).
    Image.fromarray(frame[:, :, ::-1].astype(np.uint8)).save(out)
    print(f"saved: {out}")

    verdict = "PASS (real content)" if (mean > 2 and std > 2) else "FAIL (looks black)"
    print(f"verdict: {verdict}")
    return 0 if verdict.startswith("PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
