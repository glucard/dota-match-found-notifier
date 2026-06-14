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

    If ``monitor`` is True, no notifications are sent: the pixel backend shows a
    live match bar; the console backend just prints when it would fire.
    """
    backend = cfg.detector.backend.lower()

    # Only the pixel backend needs a screen capturer.
    cap = make_capturer(cfg.capture) if backend == "pixel" else None
    det = make_detector(cfg, cap)

    err = det.preflight()
    if err:
        ui.error(err)
        return 1

    notifier = make_notifier(cfg.ntfy)
    stopper = _Stopper()
    det.start()

    can_measure = isinstance(det, PixelDetector)
    use_live = monitor and can_measure
    # Console detection is latched (fires once, then poll() returns None), so a
    # multi-frame streak would never confirm — it must fire on the first hit.
    need = 1 if backend == "console" else cfg.runtime.confirm_frames

    if use_live:
        ui.panel(
            "Live tuning — no notifications are sent.\n"
            "[muted]Trigger the ACCEPT popup; the bar should spike past[/] "
            f"[key]{cfg.calibration.min_fraction * 100:.0f}%[/] [muted]and hold.[/]\n"
            "[muted]Press Ctrl-C to stop.[/]",
            title="d2kit · monitor",
            style="info",
        )
    elif monitor:  # console monitor
        ui.panel(
            "Live test — no notifications are sent.\n"
            "[muted]Reading Dota's Game Coordinator log. Trigger a ready-check "
            "(a custom arcade\nlobby works, penalty-free) and you'll see "
            "[/][ok]DETECTED[/][muted]. Ctrl-C to stop.[/]",
            title="d2kit · monitor (console)",
            style="info",
        )
    else:
        visible = (
            "Reads Dota's Game Coordinator log — works even minimized."
            if backend == "console"
            else "Keep Dota visible while you queue."
        )
        ui.panel(
            f"Watching for a found match…\n[muted]{visible} Press Ctrl-C to stop.[/]\n"
            f"[muted]notifying[/] [topic]{cfg.ntfy.topic}[/] [muted]·[/] "
            f"[muted]{cfg.ntfy.server}[/]",
            title="d2kit · watching",
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
                    assert isinstance(det, PixelDetector) and live is not None  # narrowing
                    try:
                        frac = det.measure()
                    except Exception as exc:
                        log.warning("measure error: %s", exc)
                        time.sleep(cfg.runtime.poll_interval)
                        continue
                    streak = streak + 1 if frac >= cfg.calibration.min_fraction else 0
                    live.update(
                        _monitor_line(frac, streak, need, cfg.calibration.min_fraction),
                        refresh=True,
                    )
                    time.sleep(cfg.runtime.poll_interval)
                    continue

                try:
                    event = det.poll()
                except Exception as exc:  # never let a transient error kill us
                    log.warning("poll error: %s", exc)
                    event = None

                streak = streak + 1 if event else 0
                confirmed = event is not None and streak >= need

                if confirmed and (now - last_fired) > cfg.runtime.cooldown:
                    if monitor:
                        ui.console.print("[ok]🎯 DETECTED[/] [muted](monitor — not notifying)[/]")
                    else:
                        log.info("[ok]🎮 Match found![/] — notifying your phone")
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
