"""Verify the console.log match-detection logic in real time (Linux).

Tails Dota's console.log, shows activity live, and prints a loud DETECTION
banner when a line matches a trigger. Default trigger is the ready-up message
family, which fires when the "Accept" popup appears.

Test it PENALTY-FREE: create a custom arcade game — it produces the same
ready-up messages (k_EMsgGCReadyUp / k_EMsgGCReadyUpStatus) that matchmaking
uses. No need to queue or decline anything.

Setup: Dota launch options must include  -condebug  (then restart Dota).

Usage:
  uv run python scripts/verify_console_detect.py
  uv run python scripts/verify_console_detect.py --all          # print every line
  uv run python scripts/verify_console_detect.py --trigger k_EMsgGCReadyUp --trigger FoundMatch
  uv run python scripts/verify_console_detect.py --from-start   # also scan existing log
"""

from __future__ import annotations

import argparse
import os
import time

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

DEFAULT_LOG = (
    "/home/glucas/.local/share/Steam/steamapps/common/"
    "dota 2 beta/game/dota/console.log"
)
# Substring(s) that mark a found match / ready-check. "k_EMsgGCReadyUp" matches
# both k_EMsgGCReadyUp and k_EMsgGCReadyUpStatus.
DEFAULT_TRIGGERS = ["k_EMsgGCReadyUp"]

# When not --all, only these (dim) context lines are shown, to cut log noise.
INTERESTING = ("gcclient", "lobby", "readyup", "socache", "matchmaking", "party")

console = Console()


def _is_interesting(line: str) -> bool:
    low = line.lower()
    return any(k in low for k in INTERESTING)


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--log", default=DEFAULT_LOG)
    ap.add_argument(
        "--trigger",
        action="append",
        dest="triggers",
        help="substring to detect (repeatable; default: k_EMsgGCReadyUp)",
    )
    ap.add_argument("--all", action="store_true", help="print every new line, not just GC/lobby")
    ap.add_argument("--from-start", action="store_true", help="also scan existing log content")
    ap.add_argument("--cooldown", type=float, default=5.0, help="seconds between detections")
    args = ap.parse_args()
    triggers = args.triggers or DEFAULT_TRIGGERS

    console.print(
        Panel.fit(
            f"Watching  [cyan]{args.log}[/]\n"
            f"Triggers  [bold]{', '.join(triggers)}[/]\n\n"
            "[dim]Create a custom arcade game to test (penalty-free) — same ready-up\n"
            "messages as matchmaking. Ctrl-C to stop.[/]",
            title="console detection verifier",
            border_style="magenta",
        )
    )

    src = None
    inode = None
    pos = 0
    hits = 0
    last_hit = 0.0
    seek_end = not args.from_start
    waited_msg = False

    try:
        while True:
            try:
                st = os.stat(args.log)
            except FileNotFoundError:
                if src is not None:
                    src.close()
                    src = None
                if not waited_msg:
                    console.print(
                        "[yellow]waiting for console.log… is Dota running with "
                        "-condebug?[/]"
                    )
                    waited_msg = True
                time.sleep(1)
                continue
            waited_msg = False

            if src is None or st.st_ino != inode:  # first open or rotated
                if src is not None:
                    src.close()
                src = open(args.log, encoding="utf-8", errors="replace")  # noqa: SIM115
                inode = st.st_ino
                if seek_end:
                    src.seek(0, os.SEEK_END)
                    pos = src.tell()
                    seek_end = False
                else:
                    pos = 0

            if st.st_size < pos:  # truncated
                pos = 0

            src.seek(pos)
            chunk = src.read()
            pos = src.tell()

            if not chunk:
                time.sleep(0.25)
                continue

            for line in chunk.splitlines():
                stamp = time.strftime("%H:%M:%S")
                matched = next((t for t in triggers if t in line), None)
                if matched:
                    hits += 1
                    now = time.monotonic()
                    fresh = now - last_hit > args.cooldown
                    last_hit = now
                    tag = "" if fresh else "  [dim](within cooldown)[/]"
                    console.print("\a", end="")  # terminal bell
                    console.print(
                        Panel.fit(
                            Text.assemble(
                                (f"{stamp}  ", "dim"),
                                ("MATCH DETECTED", "bold green"),
                                (f"\nmatched: {matched}\n", "green"),
                                (line.strip(), "white"),
                            ),
                            title=f"🎯 detection #{hits}{tag}",
                            border_style="green",
                        )
                    )
                elif args.all or _is_interesting(line):
                    console.print(f"[dim]{stamp}  {line.strip()}[/]")
    except KeyboardInterrupt:
        console.print(f"\n[dim]stopped — {hits} detection(s).[/]")
        return 0
    finally:
        if src is not None:
            src.close()


if __name__ == "__main__":
    raise SystemExit(main())
