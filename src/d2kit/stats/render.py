"""Rich rendering: comparison table, cohort transparency, and build divergence."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from d2kit.stats.compare import Row
from d2kit.stats.divergence import Divergence
from d2kit.stats.similarity import Mode, SimilarSelection
from d2kit.ui import match_bar

# Below this many backing matches, a delta isn't trustworthy — shown dimmed.
_MIN_CONFIDENT_N = 5


def _fmt_time(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    s = round(seconds)
    sign = "-" if s < 0 else ""
    s = abs(s)
    return f"{sign}{s // 60}:{s % 60:02d}"


def _fmt_count(value: float | None) -> str:
    return "—" if value is None else f"{round(value):,}"


def _delta_cell(match: float | None, bench: float | None, kind: str, *, confident: bool) -> str:
    """Colored delta. For 'time', earlier is better; for 'count', higher is better.

    When ``confident`` is False (small sample) the delta is rendered dim instead of
    green/red, so a low-n comparison doesn't read as a strong signal.
    """
    if match is None or bench is None:
        return "[dim]—[/dim]"
    diff = match - bench
    if round(diff) == 0:
        return "[dim]±0[/dim]"
    if kind == "time":
        body = f"{_fmt_time(abs(diff))} {'earlier' if diff < 0 else 'later'}"
        better = diff < 0
    else:
        body = f"{'+' if diff > 0 else ''}{round(diff):,}"
        better = diff > 0
    if not confident:
        return f"[dim]{body}[/dim]"
    color = "green" if better else "red"
    return f"[{color}]{body}[/{color}]"


def _fmt_position(position: str | None) -> str:
    """'POSITION_1' -> 'Pos 1'."""
    if position and position.startswith("POSITION_"):
        return f"Pos {position.removeprefix('POSITION_')}"
    return "all roles"


_MODE_LABEL: dict[Mode, str] = {
    "strict": "closely matching builds",
    "relaxed": "loosened build match",
    "top_n": "closest available builds",
    "unfiltered": "all builds (no role/build match)",
}


def render_comparison(
    console: Console,
    rows: list[Row],
    *,
    hero_name: str,
    match_id: int,
    personal_n: int,
    pro_n: int,
    position: str | None = None,
) -> None:
    table = Table(
        title=f"{hero_name} · {_fmt_position(position)} — match {match_id}", title_style="bold cyan"
    )
    table.add_column("Metric")
    table.add_column("This match", justify="right")
    table.add_column(f"You (n={personal_n})", justify="right")
    table.add_column(f"Pro (n={pro_n})", justify="right")
    table.add_column("Pro n", justify="right")
    table.add_column("Δ vs You", justify="right")
    table.add_column("Δ vs Pro", justify="right")

    for row in rows:
        fmt = _fmt_time if row.kind == "time" else _fmt_count
        pro_confident = (row.pro_n or 0) >= _MIN_CONFIDENT_N
        you_confident = (row.personal_n or 0) >= _MIN_CONFIDENT_N
        row_n = "" if row.pro_n is None else f"[dim]{row.pro_n}[/dim]"
        table.add_row(
            row.label,
            fmt(row.match),
            fmt(row.personal),
            fmt(row.pro),
            row_n,
            _delta_cell(row.match, row.personal, row.kind, confident=you_confident),
            _delta_cell(row.match, row.pro, row.kind, confident=pro_confident),
        )
    console.print(table)
    console.print(
        "[dim]Times: when the milestone was hit (earlier = better). "
        "CS / net worth: higher = better. Greyed Δ = too few games (n<5) to trust.[/dim]"
    )


def render_cohort_info(console: Console, personal: SimilarSelection, pro: SimilarSelection) -> None:
    """Panel describing which matches the comparison actually used."""
    body = Text()

    pro_line = f"Pros: {len(pro.matches)} games · {pro.distinct_players} players"
    if pro.win_rate is not None:
        pro_line += f" · {pro.win_rate:.0%} win rate"
    pro_line += f"  [{_MODE_LABEL[pro.mode]}]"
    body.append(pro_line + "\n", style="bold")
    if pro.position_pool != len(pro.matches):
        body.append(
            f"  (from {pro.position_pool} same-role games, narrowed to your build)\n", style="dim"
        )
    for name, count in pro.top_contributors:
        body.append(f"  • {name} ({count})\n", style="dim")

    body.append(
        f"You: {len(personal.matches)} similar games  [{_MODE_LABEL[personal.mode]}]",
        style="bold",
    )

    console.print(Panel.fit(body, title="Compared against", border_style="magenta", padding=(0, 1)))


def render_divergence(console: Console, div: Divergence) -> None:
    """Analytic view of where your build diverges from similar pros (no advice)."""
    if not div.missing and not div.unusual:
        console.print("[dim]Your build matches what similar pros bought.[/dim]")
        return

    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("item")
    table.add_column("bar")
    table.add_column("note")

    for d in div.missing:
        name = d.item.replace("_", " ").title()
        table.add_row(
            f"[red]{name}[/red]",
            match_bar(d.pct),
            Text.from_markup(
                f"[dim]{d.pct:.0%} of similar pro builds bought it by your game's end — "
                f"you didn't (n={d.n})[/dim]"
            ),
        )
    for d in div.unusual:
        name = d.item.replace("_", " ").title()
        table.add_row(
            f"[yellow]{name}[/yellow]",
            match_bar(d.pct),
            Text.from_markup(
                f"[dim]you bought it; only {d.pct:.0%} of similar pro builds did (n={d.n})[/dim]"
            ),
        )

    console.print(
        Panel.fit(table, title="Build divergence", border_style="magenta", padding=(0, 1))
    )
