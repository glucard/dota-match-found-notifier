"""Discovery probe for Dota 2's -netconport console (Linux).

Goal: find out what (if anything) Dota prints to its console when a match is
found / the ACCEPT ready-check appears. That line is what a future NetconDetector
would match on. This tool just connects, streams everything with timestamps, and
highlights words that might be relevant so you can spot the moment.

SETUP (one time):
  1. Steam -> right-click Dota 2 -> Properties -> Launch Options
  2. Add:  -netconport 28000
  3. Fully restart Dota 2.

USE:
  uv run python scripts/netcon_probe.py            # connect to 127.0.0.1:28000
  uv run python scripts/netcon_probe.py --port 28000 --log /tmp/netcon.log

  Then queue a match. When the ACCEPT popup appears, watch the output (and the
  log file) for any new line that shows up at that exact moment. You can also
  type console commands + Enter to send them (e.g. `developer 1`, `status`,
  `con_filter_enable 0`) to coax out more output. Ctrl-C to quit.

Note: the port is local (127.0.0.1). Keep it that way — don't expose it.
"""

from __future__ import annotations

import argparse
import select
import socket
import sys
import time

# Words that *might* accompany a found match — highlighted to catch your eye.
# We don't rely on these; the point is to discover the real line.
HINTS = (
    "match",
    "ready",
    "accept",
    "found",
    "popup",
    "mminfo",
    "matchmaking",
    "ready_up",
    "readycheck",
    "sound",
    "playsound",
    "notification",
    "lobby",
    "queue",
    "pool",
)


def _stamp() -> str:
    return time.strftime("%H:%M:%S")


def _highlight(line: str) -> str:
    low = line.lower()
    if any(h in low for h in HINTS):
        return f"\x1b[1;33m{line}\x1b[0m"  # bold yellow
    return line


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=28000)
    ap.add_argument("--log", help="also append raw lines (with timestamps) to this file")
    args = ap.parse_args()

    try:
        sock = socket.create_connection((args.host, args.port), timeout=5)
    except OSError as exc:
        print(
            f"Could not connect to {args.host}:{args.port} ({exc}).\n"
            "Is Dota running with launch option  -netconport "
            f"{args.port}  ? Restart Dota after adding it.",
            file=sys.stderr,
        )
        return 1

    print(
        f"Connected to {args.host}:{args.port}. Queue a match and watch for new lines.\n"
        "Type a console command + Enter to send it. Ctrl-C to quit.\n"
    )
    log = open(args.log, "a", encoding="utf-8") if args.log else None  # noqa: SIM115
    sock.setblocking(False)
    buf = b""
    try:
        while True:
            readable, _, _ = select.select([sock, sys.stdin], [], [], 0.5)
            for src in readable:
                if src is sock:
                    try:
                        data = sock.recv(65536)
                    except BlockingIOError:
                        continue
                    if not data:
                        print("\n[connection closed by Dota]", file=sys.stderr)
                        return 0
                    buf += data
                    while b"\n" in buf:
                        raw, buf = buf.split(b"\n", 1)
                        line = raw.decode("utf-8", "replace").rstrip("\r")
                        out = f"{_stamp()}  {line}"
                        print(_highlight(out), flush=True)
                        if log:
                            log.write(out + "\n")
                            log.flush()
                else:  # stdin -> send as a console command
                    cmd = sys.stdin.readline()
                    if cmd:
                        sock.sendall(cmd.encode("utf-8"))
    except KeyboardInterrupt:
        print("\nbye")
        return 0
    finally:
        sock.close()
        if log:
            log.close()


if __name__ == "__main__":
    raise SystemExit(main())
