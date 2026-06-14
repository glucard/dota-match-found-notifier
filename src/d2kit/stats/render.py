"""Rich rendering of the comparison: this match | your mean | pro mean | deltas."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

from d2kit.stats.compare import Row


def _fmt_time(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    s = round(seconds)
    sign = "-" if s < 0 else ""
    s = abs(s)
    return f"{sign}{s // 60}:{s % 60:02d}"


def _fmt_count(value: float | None) -> str:
    return "—" if value is None else f"{round(value):,}"


def _delta_cell(match: float | None, bench: float | None, kind: str) -> str:
    """Colored delta. For 'time', earlier is better; for 'count', higher is better."""
    if match is None or bench is None:
        return "[dim]—[/dim]"
    diff = match - bench
    if round(diff) == 0:
        return "[dim]±0[/dim]"
    better = diff < 0 if kind == "time" else diff > 0
    color = "green" if better else "red"
    if kind == "time":
        body = f"{_fmt_time(abs(diff))} {'earlier' if diff < 0 else 'later'}"
    else:
        body = f"{'+' if diff > 0 else ''}{round(diff):,}"
    return f"[{color}]{body}[/{color}]"


def render_comparison(
    console: Console,
    rows: list[Row],
    *,
    hero_name: str,
    match_id: int,
    personal_n: int,
    pro_n: int,
) -> None:
    table = Table(title=f"{hero_name} — match {match_id}", title_style="bold cyan")
    table.add_column("Metric")
    table.add_column("This match", justify="right")
    table.add_column(f"You (n={personal_n})", justify="right")
    table.add_column(f"Pro (n={pro_n})", justify="right")
    table.add_column("Δ vs You", justify="right")
    table.add_column("Δ vs Pro", justify="right")

    for row in rows:
        fmt = _fmt_time if row.kind == "time" else _fmt_count
        table.add_row(
            row.label,
            fmt(row.match),
            fmt(row.personal),
            fmt(row.pro),
            _delta_cell(row.match, row.personal, row.kind),
            _delta_cell(row.match, row.pro, row.kind),
        )
    console.print(table)
    console.print(
        "[dim]Times: when the milestone was hit (earlier = better). "
        "CS / net worth: higher = better.[/dim]"
    )
