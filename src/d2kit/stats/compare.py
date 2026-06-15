"""Compare one match against the personal and pro-pub benchmark medians.

Produces a flat list of rows (checkpoints + item timings) for the renderer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from d2kit.stats.benchmark import Aggregate
from d2kit.stats.similarity import SIGNIFICANT_COST
from d2kit.stats.timings import MatchTimings

# Minute checkpoints and hero levels worth eyeballing.
_NET_WORTH_MINUTES = (10, 20)
_CS_MINUTES = (10, 20)
_HERO_DAMAGE_MINUTES = (20,)
_TOWER_DAMAGE_MINUTES = (20,)
_LEVELS = (6, 12, 18)
_MAX_ITEM_ROWS = 15


@dataclass(frozen=True)
class Row:
    label: str
    match: float | None
    personal: float | None
    pro: float | None
    kind: Literal["time", "count"]
    # Per-row benchmark sample size (how many pool matches backed each median).
    personal_n: int | None = None
    pro_n: int | None = None


def build_rows(
    match: MatchTimings, personal: Aggregate, pro: Aggregate, cost_by_name: dict[str, int]
) -> list[Row]:
    rows: list[Row] = []

    for minute in _CS_MINUTES:
        rows.append(
            Row(
                f"CS @ {minute}m",
                match.last_hits_at(minute),
                personal.last_hits_at(minute),
                pro.last_hits_at(minute),
                "count",
                personal.last_hits_n_at(minute),
                pro.last_hits_n_at(minute),
            )
        )
    for minute in _NET_WORTH_MINUTES:
        rows.append(
            Row(
                f"Net worth @ {minute}m",
                match.networth_at(minute),
                personal.networth_at(minute),
                pro.networth_at(minute),
                "count",
                personal.networth_n_at(minute),
                pro.networth_n_at(minute),
            )
        )
    for minute in _HERO_DAMAGE_MINUTES:
        rows.append(
            Row(
                f"Hero dmg @ {minute}m",
                match.hero_damage_at(minute),
                personal.hero_damage_at(minute),
                pro.hero_damage_at(minute),
                "count",
                personal.hero_damage_n_at(minute),
                pro.hero_damage_n_at(minute),
            )
        )
    for minute in _TOWER_DAMAGE_MINUTES:
        rows.append(
            Row(
                f"Structure dmg @ {minute}m",
                match.tower_damage_at(minute),
                personal.tower_damage_at(minute),
                pro.tower_damage_at(minute),
                "count",
                personal.tower_damage_n_at(minute),
                pro.tower_damage_n_at(minute),
            )
        )
    for level in _LEVELS:
        rows.append(
            Row(
                f"Level {level}",
                match.level_time(level),
                personal.level_time(level),
                pro.level_time(level),
                "time",
                personal.level_n(level),
                pro.level_n(level),
            )
        )

    # Only the analyzed match's "build" items (cost ≥ threshold), earliest first.
    item_rows = [
        (item, time)
        for item, time in match.item_timings.items()
        if cost_by_name.get(item, 0) >= SIGNIFICANT_COST
    ]
    item_rows.sort(key=lambda kv: kv[1])
    for item, time in item_rows[:_MAX_ITEM_ROWS]:
        rows.append(
            Row(
                item.replace("_", " ").title(),
                float(time),
                personal.item_medians.get(item),
                pro.item_medians.get(item),
                "time",
                personal.item_counts.get(item, 0),
                pro.item_counts.get(item, 0),
            )
        )
    return rows
