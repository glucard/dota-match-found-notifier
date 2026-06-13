"""Diagnose PipeWire frame freshness.

Pick 'Entire Screen' in the picker, then DON'T touch the mouse/keyboard for a
few seconds, then move the mouse around for the rest. We log, per poll, whether
get_frame() returned a frame and whether it changed vs the previous one. This
reveals if the stream only delivers frames on screen change (damage-based).

Usage:  uv run python scripts/diag_frames.py
"""

from __future__ import annotations

import time

import numpy as np
import pipewire_capture as pw

DURATION = 10.0
INTERVAL = 0.15


def main() -> int:
    portal = pw.PortalCapture()
    session = portal.select_window()
    if session is None:
        print("cancelled")
        return 1
    stream = pw.CaptureStream(
        session.fd, session.node_id, session.width, session.height, capture_interval=0.1
    )
    stream.start()
    print(f"{session.width}x{session.height}  capture_interval=0.1  poll={INTERVAL}s")
    print("Stay STILL for ~5s, then move the mouse. Watching frame freshness...\n")

    prev = None
    t0 = time.monotonic()
    none_count = changed = same = 0
    while time.monotonic() - t0 < DURATION:
        f = stream.get_frame()
        tag = ""
        if f is None:
            none_count += 1
            tag = "None"
        else:
            arr = np.asarray(f)
            if prev is not None and arr.shape == prev.shape and np.array_equal(arr, prev):
                same += 1
                tag = "same-as-prev"
            else:
                changed += 1
                tag = "FRESH"
            prev = arr
        print(f"  t={time.monotonic() - t0:4.1f}s  {tag}")
        time.sleep(INTERVAL)

    stream.stop()
    session.close()
    print(f"\nsummary: None={none_count}  FRESH={changed}  same-as-prev={same}")
    print(
        "If long runs of 'same-as-prev' happen while still and 'FRESH' only when "
        "you move the mouse -> delivery is damage-based (the root cause)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
