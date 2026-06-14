"""Extract the four metric families from a STRATZ match-player payload.

All times are in seconds from the horn (negative = pre-horn purchases).
"""

from __future__ import annotations

from itertools import accumulate
from typing import Any

from pydantic import BaseModel


class MatchTimings(BaseModel):
    """Timings for one player in one match."""

    match_id: int
    hero_id: int
    # First-purchase time (seconds) per item shortName, e.g. {"blink": 540}.
    item_timings: dict[str, int]
    # Index = minute. Net worth is STRATZ's cumulative value at that minute; last
    # hits are accumulated at extraction (STRATZ ships them as per-minute deltas).
    networth_per_min: list[int]
    cumulative_last_hits: list[int]
    # Index i = seconds to reach hero level i+1.
    level_timings: list[int]

    def last_hits_at(self, minute: int) -> int | None:
        """Cumulative last hits at ``minute`` (e.g. CS@10), or None if too short."""
        return (
            self.cumulative_last_hits[minute] if minute < len(self.cumulative_last_hits) else None
        )

    def networth_at(self, minute: int) -> int | None:
        return self.networth_per_min[minute] if minute < len(self.networth_per_min) else None

    def level_time(self, level: int) -> int | None:
        """Seconds to reach hero ``level`` (1-indexed), or None if never reached."""
        idx = level - 1
        return self.level_timings[idx] if 0 <= idx < len(self.level_timings) else None


def extract_timings(
    match_id: int,
    player: dict[str, Any],
    item_names: dict[int, str],
) -> MatchTimings:
    """Build :class:`MatchTimings` from a match player object + item id->name map.

    Only the *first* purchase time of each item is kept (consumables bought
    repeatedly collapse to their earliest buy, which is what timings care about).
    """
    stats = player.get("stats") or {}

    item_timings: dict[str, int] = {}
    for purchase in stats.get("itemPurchases") or []:
        name = item_names.get(purchase["itemId"])
        if name is None:
            continue
        time = purchase["time"]
        if name not in item_timings or time < item_timings[name]:
            item_timings[name] = time

    learn_events = (player.get("playbackData") or {}).get("abilityLearnEvents") or []
    # Nth learn event (ordered by time) == reaching hero level N.
    level_timings = [ev["time"] for ev in sorted(learn_events, key=lambda e: e["time"])]

    # STRATZ ships last hits as per-minute gains; accumulate to get CS-at-minute.
    last_hits_per_min = stats.get("lastHitsPerMinute") or []
    cumulative_last_hits = list(accumulate(last_hits_per_min))

    return MatchTimings(
        match_id=match_id,
        hero_id=player["heroId"],
        item_timings=item_timings,
        networth_per_min=stats.get("networthPerMinute") or [],
        cumulative_last_hits=cumulative_last_hits,
        level_timings=level_timings,
    )
