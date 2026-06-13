"""Headless watch loop: capture -> detect -> notify, with confirmation + cooldown."""

from __future__ import annotations

import logging
import signal
import time
from contextlib import nullcontext

from rich.live import Live
from rich.text import Text

from . import ui
from .capture import make_capturer
from .config import Config
from .detect import make_detector
from .detect.pixel import PixelDetector
from .notify import make_notifier

log = logging.getLogger(__name__)


class _Stopper:
    """Flips to stopped on SIGINT/SIGTERM so the loop exits cleanly."""

    def __init__(self) -> None:
        self.stop = False
        signal.signal(signal.SIGINT, self._handle)
        signal.signal(signal.SIGTERM, self._handle)

    def _handle(self, *_a: object) -> None:
        self.stop = True


def _monitor_line(frac: float, streak: int, need: int, min_fraction: float) -> Text:
    """One live-updating row: a bar, the percentage, and the confirm status."""
    is_hit = frac >= min_fraction
    if streak >= need:
        status = Text("  ✓ WOULD NOTIFY", style="ok")
    elif is_hit:
        status = Text(f"  holding {streak}/{need}", style="warn")
    else:
        status = Text("  waiting for popup", style="muted")
    return Text.assemble(
        Text("match ", style="muted"),
        ui.match_bar(frac),
        Text(f" {frac * 100:5.1f}%", style="key"),
        status,
    )


def run(cfg: Config, monitor: bool = False) -> int:
    """Run the watch loop.

    If ``monitor`` is True, show the live match fraction every poll and do not
    send notifications — useful for tuning ``tolerance``/``min_fraction``.
    """
    if not cfg.calibration.calibrated:
        ui.error("Not calibrated yet. Run  [accent]d2aa --config[/]  first.")
        return 1

    cap = make_capturer(cfg.capture)
    det = make_detector(cfg, cap)
    notifier = make_notifier(cfg.ntfy)

    stopper = _Stopper()
    det.start()

    can_measure = isinstance(det, PixelDetector)
    use_live = monitor and can_measure

    if use_live:
        ui.panel(
            f"Live tuning — no notifications are sent.\n"
            f"[muted]Trigger the ACCEPT popup; the bar should spike past[/] "
            f"[key]{cfg.calibration.min_fraction * 100:.0f}%[/] [muted]and hold.[/]\n"
            f"[muted]Press Ctrl-C to stop.[/]",
            title="d2aa · monitor",
            style="info",
        )
    else:
        ui.panel(
            f"Watching for a found match…\n"
            f"[muted]Keep Dota visible while you queue. Press Ctrl-C to stop.[/]\n"
            f"[muted]notifying[/] [topic]{cfg.ntfy.topic}[/] [muted]·[/] "
            f"[muted]{cfg.ntfy.server}[/]",
            title="d2aa · watching",
            style="ok",
        )

    streak = 0
    last_fired = 0.0
    live_cm = Live(console=ui.console, auto_refresh=False) if use_live else nullcontext()
    try:
        with live_cm as live:
            while not stopper.stop:
                now = time.monotonic()

                if use_live:
                    try:
                        frac = det.measure()
                    except Exception as exc:
                        log.warning("measure error: %s", exc)
                        time.sleep(cfg.runtime.poll_interval)
                        continue
                    need = cfg.runtime.confirm_frames
                    streak = streak + 1 if frac >= cfg.calibration.min_fraction else 0
                    live.update(
                        _monitor_line(frac, streak, need, cfg.calibration.min_fraction),
                        refresh=True,
                    )
                    time.sleep(cfg.runtime.poll_interval)
                    continue

                try:
                    event = det.poll()
                except Exception as exc:  # never let a transient capture error kill us
                    log.warning("poll error: %s", exc)
                    event = None

                # Require N consecutive positive polls before firing.
                streak = streak + 1 if event else 0
                confirmed = event is not None and streak >= cfg.runtime.confirm_frames

                if confirmed and (now - last_fired) > cfg.runtime.cooldown:
                    log.info(
                        "[ok]🎮 Match found![/] (%.0f%% over %d frames) — notifying your phone",
                        event.confidence * 100,
                        streak,
                    )
                    notifier.send(
                        title="Match Found!",
                        message="Dota 2 — return to the PC and accept.",
                        priority=cfg.ntfy.priority,
                        tags=cfg.ntfy.tags,
                        click=cfg.ntfy.click or None,
                    )
                    last_fired = now

                time.sleep(cfg.runtime.poll_interval)
    finally:
        det.stop()

    ui.console.print("[muted]Stopped.[/]")
    return 0
