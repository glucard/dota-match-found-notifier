"""Centralized terminal UI built on rich.

All user-facing output goes through here so styling stays consistent and lives in
one place. This module is presentation only — it never changes program behavior.
Output degrades gracefully when stdout isn't a TTY (rich disables color/animation
automatically), which matters for the frozen binary and piped logs.
"""

from __future__ import annotations

import logging

from rich.console import Console, RenderableType
from rich.logging import RichHandler
from rich.panel import Panel
from rich.text import Text
from rich.theme import Theme

THEME = Theme(
    {
        "info": "cyan",
        "ok": "bold green",
        "warn": "yellow",
        "err": "bold red",
        "accent": "bold magenta",
        "topic": "bold cyan",
        "muted": "dim",
        "key": "bold white",
    }
)

console = Console(theme=THEME)
err_console = Console(theme=THEME, stderr=True)

# Brand mark reused across panels.
APP_TITLE = "[accent]d2aa[/] [muted]· Dota 2 match-found notifier[/]"


def setup_logging(verbose: bool) -> None:
    """Route logging through rich for clean, colored, timestamped lines."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[
            RichHandler(
                console=err_console,
                show_path=False,
                show_level=True,
                markup=True,
                rich_tracebacks=True,
                omit_repeated_times=False,
            )
        ],
    )


def panel(body: RenderableType, *, title: str | None = None, style: str = "accent") -> None:
    console.print(Panel.fit(body, title=title, border_style=style, padding=(0, 1)))


def error(message: str) -> None:
    """Friendly error block to stderr."""
    err_console.print(f"[err]✗[/] {message}")


def color_swatch(rgb: list[int]) -> Text:
    """A small colored block showing an RGB color, plus its value."""
    r, g, b = rgb
    block = Text("  ", style=f"on rgb({r},{g},{b})")
    return Text.assemble(block, Text(f" RGB({r}, {g}, {b})", style="muted"))


def match_bar(fraction: float, *, width: int = 24) -> Text:
    """A horizontal bar for a 0..1 match fraction, colored by strength."""
    filled = max(0, min(width, round(fraction * width)))
    if fraction >= 0.6:
        color = "green"
    elif fraction >= 0.3:
        color = "yellow"
    else:
        color = "red"
    bar = Text()
    bar.append("█" * filled, style=color)
    bar.append("░" * (width - filled), style="muted")
    return bar
