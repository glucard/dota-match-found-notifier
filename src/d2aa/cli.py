"""Command-line entry point.

d2aa            run the headless watcher (needs prior calibration)
d2aa --config   open the calibration wizard
d2aa --test     send a test notification to verify the phone setup
"""

from __future__ import annotations

import argparse
import sys

from . import app, ui
from .config import ConfigError, load
from .gui import wizard
from .notify import make_notifier

_DESCRIPTION = "Notify your phone when Dota 2 finds a match — so you can step away while queuing."

_EPILOG = """\
examples:
  d2aa --config     set up once (calibrate + get your phone topic)
  d2aa --test       send a test push to confirm your phone is set up
  d2aa              watch for a found match and notify
  d2aa --monitor    tune detection without notifying (shows live match %)
"""


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
    parser.add_argument("-v", "--verbose", action="store_true", help="enable debug logging")
    args = parser.parse_args()

    ui.setup_logging(args.verbose)

    if args.config:
        return wizard.run()

    try:
        cfg = load()
    except ConfigError as exc:
        ui.error(str(exc))
        return 1

    if args.test:
        ui.console.print("[muted]Sending a test notification…[/]")
        make_notifier(cfg.ntfy).send(
            title="d2aa test ✅",
            message="If you see this on your phone, notifications work!",
            priority=cfg.ntfy.priority,
            tags=cfg.ntfy.tags,
        )
        ui.console.print(
            f"[ok]✓ Test sent.[/] Check your phone for the [topic]ntfy[/] notification.\n"
            f"  [muted]topic[/] [topic]{cfg.ntfy.topic}[/]  [muted]·[/]  "
            f"[muted]{cfg.ntfy.server}[/]"
        )
        return 0

    return app.run(cfg, monitor=args.monitor)


if __name__ == "__main__":
    sys.exit(run())
