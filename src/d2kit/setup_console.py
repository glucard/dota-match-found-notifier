"""Terminal setup for the console (Game Coordinator log) detector.

Parallel to the pixel calibration wizard, but there's nothing to calibrate: we
just confirm Dota's console.log is reachable (it needs the launch options
``-condebug -conclearlog``), select the console backend, and make sure a phone
topic exists. Works on Linux and Windows. No tkinter, no screen capture.
"""

from __future__ import annotations

import sys

from . import ui
from .config import Config, load, new_topic, save
from .detect.console import candidate_paths, resolve_console_log


def _carry_config() -> Config:
    """Fresh config with current defaults, keeping any existing ntfy settings."""
    cfg = Config()
    try:
        old = load()
    except Exception:
        return cfg
    if old.ntfy.topic:
        cfg.ntfy = old.ntfy
    return cfg


def run() -> int:
    ui.panel(
        "Reads Dota's [topic]Game Coordinator[/] log to catch the ready-check the\n"
        "instant it appears — no screen capture, no calibration, works even when\n"
        "Dota is minimized. (Linux & Windows.)",
        title="d2kit · console setup",
        style="accent",
    )

    path = resolve_console_log("auto")
    if path is None:
        paths = candidate_paths()
        searched = (
            "\n  ".join(f"[muted]{p}[/]" for p in paths)
            if paths
            else "[muted](no Steam install found)[/]"
        )
        ui.panel(
            "Couldn't find Dota's [topic]console.log[/] yet.\n\n"
            "[key]1.[/] Steam → Dota 2 → Properties → Launch Options\n"
            "[key]2.[/] Add:  [accent]-condebug -conclearlog[/]\n"
            "[key]3.[/] Start Dota once, then run this setup again.\n\n"
            f"[muted]Looked in:[/]\n  {searched}",
            title="⚠ Set launch options first",
            style="warn",
        )
        return 1

    ui.console.print(f"[ok]✓[/] Found console.log:  [topic]{path}[/]")

    cfg = _carry_config()
    cfg.detector.backend = "console"
    cfg.detector.console.log_path = "auto"
    if not cfg.ntfy.topic:
        cfg.ntfy.topic = new_topic()
    saved = save(cfg)

    ui.panel(
        f"Console detection is now your method.\n[muted]config: {saved}[/]",
        title="✓ Saved",
        style="ok",
    )

    from .menu import show_phone_setup  # lazy import to avoid a cycle

    show_phone_setup(cfg)
    ui.console.print(
        "\n[muted]Test it penalty-free: create a custom arcade lobby (same ready-up\n"
        "messages as matchmaking) and use[/] [accent]Tune detection[/] "
        "[muted]to watch it fire.[/]"
    )
    return 0


if __name__ == "__main__":
    sys.exit(run())
