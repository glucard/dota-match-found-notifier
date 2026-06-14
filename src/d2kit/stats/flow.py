"""Interactive "compare a match" flow for the stats tool.

Adapted from the standalone dota-stats menu, but reads the unified d2kit config.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import questionary
from rich.console import Console

from ..config import Config, resolve_token
from . import benchmark, cohort
from .compare import build_rows
from .render import render_comparison
from .stratz import StratzClient, StratzError, queries
from .stratz.constants import Constants, load_constants


def compare(console: Console, cfg: Config) -> None:
    """Run one 'compare a match' interaction. Assumes token + account are set."""
    token = resolve_token(cfg)
    account_id = cfg.stats.account_id
    if not token or not account_id:
        console.print("[yellow]Set up your STRATZ token and Steam id first.[/yellow]")
        return
    try:
        with StratzClient(token) as client:
            _compare_flow(console, client, cfg, account_id)
    except StratzError as exc:
        console.print(f"[red]STRATZ error:[/red] {exc}")


def _compare_flow(console: Console, client: StratzClient, cfg: Config, account_id: int) -> None:
    # Fetch extra since Turbo games (filtered below) can dominate recent history.
    take = 40 if cfg.stats.filter_turbo else 15
    with console.status("Loading constants & your recent matches…"):
        consts = load_constants(client)
        recent = client.query(queries.PLAYER_RECENT_MATCHES, {"id": account_id, "take": take})[
            "player"
        ]["matches"]

    if cfg.stats.filter_turbo:
        recent = [m for m in recent if m.get("gameMode") != "TURBO"]
        if not recent:
            console.print(
                "[yellow]Only Turbo matches found recently.[/yellow] "
                "Turn off the Turbo filter in Set up to analyze one."
            )
            return

    pick = _pick_match(recent[:15], consts)
    if pick is None:
        return
    match_id, hero_id = pick

    with console.status("Fetching your mean, the pro cohort, and this match…"):
        # +1 so excluding the analyzed match still leaves last_n in the mean.
        personal = benchmark.fetch_personal(
            client, account_id, hero_id, consts.item_names, cfg.stats.last_n + 1
        )
        pro = benchmark.fetch_pro_cohort(
            client, hero_id, consts.item_names, cohort.pro_account_ids()
        )
        match = benchmark.fetch_match(client, match_id, account_id, consts.item_names)

    if match is None:
        console.print("[red]Could not load that match's timings.[/red]")
        return
    # Don't compare the match against a mean that includes itself.
    personal = [t for t in personal if t.match_id != match_id]
    if not personal:
        console.print("[yellow]No other matches on this hero to form your mean.[/yellow]")

    rows = build_rows(match, benchmark.aggregate(personal), benchmark.aggregate(pro))
    render_comparison(
        console,
        rows,
        hero_name=consts.hero_names.get(hero_id, f"Hero {hero_id}"),
        match_id=match_id,
        personal_n=len(personal),
        pro_n=len(pro),
    )


def _pick_match(recent: list[dict[str, Any]], consts: Constants) -> tuple[int, int] | None:
    """Present the recent-match picker; return (match_id, hero_id)."""
    labels: dict[str, tuple[int, int]] = {}
    for m in recent:
        players = m.get("players") or []
        if not players:
            continue
        p = players[0]
        hero = consts.hero_names.get(p["heroId"], f"Hero {p['heroId']}")
        result = "W" if p.get("isVictory") else "L"
        when = datetime.fromtimestamp(m["startDateTime"], tz=UTC).strftime("%Y-%m-%d")
        labels[f"{when}  {result}  {hero}  (#{m['id']})"] = (m["id"], p["heroId"])
    if not labels:
        return None
    choice = questionary.select("Which match?", choices=list(labels)).ask()
    return labels.get(choice) if choice else None
