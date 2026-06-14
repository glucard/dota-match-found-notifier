"""Command-line entry point.

With no flags in a terminal, d2kit opens an interactive menu. Flags give direct
access for power users / scripts:

  d2kit            interactive menu (or, when not a TTY, start watching)
  d2kit --config   open the calibration wizard
  d2kit --test     send a test notification to verify the phone setup
  d2kit --monitor  live detection tuning (no notifications)
  d2kit --watch    start watching immediately (skip the menu)
"""

from __future__ import annotations

import argparse
import sys

from . import app, ui
from .config import Config, ConfigError, load
from .gui import wizard
from .notify import make_notifier

_DESCRIPTION = "Dota 2 toolbox: match-found phone notifier + timing stats vs your mean and pros."

_EPILOG = """\
examples:
  d2kit              open the interactive menu (easiest)
  d2kit --config     set up the notifier (calibrate / console + phone topic)
  d2kit --test       send a test push to confirm your phone is set up
  d2kit --watch      start watching for a match (skip the menu)
  d2kit --monitor    tune detection without notifying (shows live match %)
  d2kit --stats      compare a match vs your mean + pros (STRATZ)
"""


def send_test(cfg: Config) -> None:
    """Send a test notification and report it. Shared by the flag and the menu."""
    ui.console.print("[muted]Sending a test notification…[/]")
    make_notifier(cfg.ntfy).send(
        title="d2kit test",
        message="✅ If you see this on your phone, notifications work!",
        priority=cfg.ntfy.priority,
        tags=cfg.ntfy.tags,
    )
    ui.console.print(
        f"[ok]✓ Test sent.[/] Check your phone for the [topic]ntfy[/] notification.\n"
        f"  [muted]topic[/] [topic]{cfg.ntfy.topic}[/]  [muted]·[/]  [muted]{cfg.ntfy.server}[/]"
    )


def run() -> int:
    parser = argparse.ArgumentParser(
        prog="d2kit",
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
    parser.add_argument(
        "--stats", action="store_true", help="jump straight to the stats match comparison"
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="enable debug logging")
    args = parser.parse_args()

    ui.setup_logging(args.verbose)

    if args.config:
        try:
            backend = load().detector.backend.lower()
        except ConfigError:
            backend = "pixel"
        if backend == "console":
            from . import setup_console

            return setup_console.run()
        return wizard.run()

    # No explicit action + an interactive terminal -> the friendly menu.
    explicit = args.test or args.monitor or args.watch or args.stats
    interactive = sys.stdin.isatty() and sys.stdout.isatty()
    if not explicit and interactive:
        from .menu import run_menu

        return run_menu()

    # Explicit flags, or a non-interactive run (pipe / CI / autostart service).
    try:
        cfg = load()
    except ConfigError as exc:
        ui.error(str(exc))
        return 1

    if args.test:
        send_test(cfg)
        return 0

    if args.stats:
        from .stats.flow import compare

        compare(ui.console, cfg)
        return 0

    # --watch, --monitor, and a bare non-TTY run all land here.
    return app.run(cfg, monitor=args.monitor)


if __name__ == "__main__":
    sys.exit(run())
