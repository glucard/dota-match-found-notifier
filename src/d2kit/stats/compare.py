"""Compare one match against the personal and pro-pub benchmark medians.

Produces a flat list of rows (checkpoints + item timings) for the renderer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from d2kit.stats.benchmark import Aggregate
from d2kit.stats.timings import MatchTimings

# Minute checkpoints and hero levels worth eyeballing.
_NET_WORTH_MINUTES = (10, 20)
_CS_MINUTES = (10, 20)
_LEVELS = (6, 12, 18)

# Low-signal items excluded from the item-timing rows (consumables / components).
_ITEM_NOISE = frozenset(
    {
        "tango",
        "faerie_fire",
        "clarity",
        "enchanted_mango",
        "branches",
        "ward_observer",
        "ward_sentry",
        "ward_dispenser",
        "tpscroll",
        "bottle",
        "flask",
        "infused_raindrop",
        "smoke_of_deceit",
        "dust",
        "gauntlets",
        "slippers",
        "circlet",
        "mantle",
        "boots",
        "recipe",
        "blade_of_alacrity",
        "belt_of_strength",
        "robe",
        "ogre_axe",
        "blades_of_attack",
        "quelling_blade",
        "magic_stick",
        "ring_of_protection",
        "gloves",
        "crown",
        "fluffy_hat",
    }
)
_MAX_ITEM_ROWS = 15


@dataclass(frozen=True)
class Row:
    label: str
    match: float | None
    personal: float | None
    pro: float | None
    kind: Literal["time", "count"]


def build_rows(match: MatchTimings, personal: Aggregate, pro: Aggregate) -> list[Row]:
    rows: list[Row] = []

    for minute in _CS_MINUTES:
        rows.append(
            Row(
                f"CS @ {minute}m",
                match.last_hits_at(minute),
                personal.last_hits_at(minute),
                pro.last_hits_at(minute),
                "count",
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
            )
        )

    item_rows = [
        (item, time) for item, time in match.item_timings.items() if item not in _ITEM_NOISE
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
            )
        )
    return rows
