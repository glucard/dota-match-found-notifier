"""Command-line entry point.

With no flags in a terminal, d2aa opens an interactive menu. Flags give direct
access for power users / scripts:

  d2aa            interactive menu (or, when not a TTY, start watching)
  d2aa --config   open the calibration wizard
  d2aa --test     send a test notification to verify the phone setup
  d2aa --monitor  live detection tuning (no notifications)
  d2aa --watch    start watching immediately (skip the menu)
"""

from __future__ import annotations

import argparse
import sys

from . import app, ui
from .config import Config, ConfigError, load
from .gui import wizard
from .notify import make_notifier

_DESCRIPTION = "Notify your phone when Dota 2 finds a match — so you can step away while queuing."

_EPILOG = """\
examples:
  d2aa              open the interactive menu (easiest)
  d2aa --config     set up once (calibrate + get your phone topic)
  d2aa --test       send a test push to confirm your phone is set up
  d2aa --watch      start watching for a match (skip the menu)
  d2aa --monitor    tune detection without notifying (shows live match %)
"""


def send_test(cfg: Config) -> None:
    """Send a test notification and report it. Shared by the flag and the menu."""
    ui.console.print("[muted]Sending a test notification…[/]")
    make_notifier(cfg.ntfy).send(
        title="d2aa test ✅",
        message="If you see this on your phone, notifications work!",
        priority=cfg.ntfy.priority,
        tags=cfg.ntfy.tags,
    )
    ui.console.print(
        f"[ok]✓ Test sent.[/] Check your phone for the [topic]ntfy[/] notification.\n"
        f"  [muted]topic[/] [topic]{cfg.ntfy.topic}[/]  [muted]·[/]  [muted]{cfg.ntfy.server}[/]"
    )


def run() -> int:
    parser = argparse.ArgumentParser(
        prog="d2aa",
        description=_DESCRIPTION,
        epilog=_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--config", action="store_true", help="run the calibration wizard")
    parser.add_argument("--test", action="store_true", help="send a test phone notification")
    parser.add_argument(
        "--monitor",
        action="store_true",
        help="show live match%% without notifying (for tuning)",
    )
    parser.add_argument(
        "--watch", action="store_true", help="start watching immediately (skip the menu)"
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="enable debug logging")
    args = parser.parse_args()

    ui.setup_logging(args.verbose)

    if args.config:
        return wizard.run()

    # No explicit action + an interactive terminal -> the friendly menu.
    explicit = args.test or args.monitor or args.watch
    interactive = sys.stdin.isatty() and sys.stdout.isatty()
    if not explicit and interactive:
        from .menu import run_menu

        return run_menu(args.verbose)

    # Explicit flags, or a non-interactive run (pipe / CI / autostart service).
    try:
        cfg = load()
    except ConfigError as exc:
        ui.error(str(exc))
        return 1

    if args.test:
        send_test(cfg)
        return 0

    # --watch, --monitor, and a bare non-TTY run all land here.
    return app.run(cfg, monitor=args.monitor)


if __name__ == "__main__":
    sys.exit(run())
