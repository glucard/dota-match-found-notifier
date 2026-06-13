"""Durably capture Dota's console.log so nothing is ever lost.

Why: we only want to trigger one real Find Match (declining a ready-check gives a
matchmaking ban). This copies the WHOLE existing console.log plus every new line
into a separate file we control, and keeps following it — surviving truncation
and log rotation (re-opens if the file is replaced or shrinks).

Usage:
  uv run python scripts/capture_console.py
  uv run python scripts/capture_console.py --out ~/d2aa_capture.log

Leave it running, do ONE Find Match, accept the popup, then stop with Ctrl-C.
The full record is in the --out file (default below).
"""

from __future__ import annotations

import argparse
import os
import sys
import time

DEFAULT_LOG = (
    "/home/glucas/.local/share/Steam/steamapps/common/"
    "dota 2 beta/game/dota/console.log"
)
DEFAULT_OUT = "/tmp/d2aa_console_capture.log"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--log", default=DEFAULT_LOG, help="path to Dota console.log")
    ap.add_argument("--out", default=DEFAULT_OUT, help="durable capture file (appended)")
    ap.add_argument("--poll", type=float, default=0.25, help="seconds between reads")
    args = ap.parse_args()

    out = open(args.out, "a", encoding="utf-8")  # noqa: SIM115 — long-lived sink
    out.write(f"\n==== capture started {time.strftime('%Y-%m-%d %H:%M:%S')} ====\n")
    out.flush()

    print(f"Capturing  {args.log}\n        -> {args.out}")
    print("Do ONE Find Match, accept the popup, then press Ctrl-C.\n")

    src = None
    inode = None
    pos = 0
    written = 0
    last_report = 0.0
    try:
        while True:
            try:
                st = os.stat(args.log)
            except FileNotFoundError:
                # log not there yet (Dota not running / no -condebug)
                if src is not None:
                    src.close()
                    src = None
                time.sleep(args.poll)
                continue

            # (Re)open on first run or if the file was replaced (rotation).
            if src is None or st.st_ino != inode:
                if src is not None:
                    src.close()
                src = open(args.log, encoding="utf-8", errors="replace")  # noqa: SIM115
                inode = st.st_ino
                pos = 0  # read from the very beginning -> capture existing history

            # Truncation: file shrank, start over from the top.
            if st.st_size < pos:
                pos = 0

            src.seek(pos)
            data = src.read()
            if data:
                out.write(data)
                out.flush()
                pos = src.tell()
                written += data.count("\n")

            now = time.monotonic()
            if now - last_report > 2:
                print(f"\r  captured {written} lines…", end="", flush=True)
                last_report = now

            if not data:
                time.sleep(args.poll)
    except KeyboardInterrupt:
        print(f"\nStopped. {written} lines saved to {args.out}")
        return 0
    finally:
        if src is not None:
            src.close()
        out.close()


if __name__ == "__main__":
    sys.exit(main())
