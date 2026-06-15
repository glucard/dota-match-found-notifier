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
    # Index = minute -> cumulative hero / structure damage (STRATZ ships per-minute
    # deltas; accumulated at extraction like last hits).
    cumulative_hero_damage: list[int]
    cumulative_tower_damage: list[int]
    # Index i = seconds to reach hero level i+1.
    level_timings: list[int]
    # Provenance / context (None on the analyzed match & personal pool, where not needed).
    account_id: int | None = None
    player_name: str | None = None
    position: str | None = None  # STRATZ MatchPlayerPositionType, e.g. "POSITION_1"
    is_victory: bool | None = None
    duration_seconds: int | None = None

    def last_hits_at(self, minute: int) -> int | None:
        """Cumulative last hits at ``minute`` (e.g. CS@10), or None if too short."""
        return (
            self.cumulative_last_hits[minute] if minute < len(self.cumulative_last_hits) else None
        )

    def networth_at(self, minute: int) -> int | None:
        return self.networth_per_min[minute] if minute < len(self.networth_per_min) else None

    def hero_damage_at(self, minute: int) -> int | None:
        """Cumulative hero damage at ``minute``, or None if the game was shorter."""
        return (
            self.cumulative_hero_damage[minute]
            if minute < len(self.cumulative_hero_damage)
            else None
        )

    def tower_damage_at(self, minute: int) -> int | None:
        """Cumulative structure damage at ``minute``, or None if the game was shorter."""
        return (
            self.cumulative_tower_damage[minute]
            if minute < len(self.cumulative_tower_damage)
            else None
        )

    def level_time(self, level: int) -> int | None:
        """Seconds to reach hero ``level`` (1-indexed), or None if never reached."""
        idx = level - 1
        return self.level_timings[idx] if 0 <= idx < len(self.level_timings) else None

    @property
    def duration_for_gate(self) -> int:
        """Game length in seconds, for duration-gated divergence.

        Uses ``duration_seconds`` when known, else falls back to the net-worth
        series length (one entry per minute) times 60.
        """
        if self.duration_seconds is not None:
            return self.duration_seconds
        return len(self.networth_per_min) * 60

    def significant_items(self, cost_by_name: dict[str, int], threshold: int) -> frozenset[str]:
        """The set of "build" items: those costing at least ``threshold`` gold.

        Cheap components/consumables (and unknown-cost items) are excluded, so the
        set captures the build identity regardless of purchase order.
        """
        return frozenset(
            item for item in self.item_timings if cost_by_name.get(item, 0) >= threshold
        )


def extract_timings(
    match_id: int,
    player: dict[str, Any],
    item_names: dict[int, str],
    *,
    account_id: int | None = None,
    player_name: str | None = None,
    duration_seconds: int | None = None,
) -> MatchTimings:
    """Build :class:`MatchTimings` from a match player object + item id->name map.

    Only the *first* purchase time of each item is kept (consumables bought
    repeatedly collapse to their earliest buy, which is what timings care about).
    ``position``/``is_victory`` are read from ``player`` when present;
    ``account_id``/``player_name``/``duration_seconds`` come from the surrounding
    payload (the cohort query carries them at the player/match nodes).
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

    # STRATZ ships last hits / damage as per-minute gains; accumulate to get
    # the cumulative value at each minute.
    cumulative_last_hits = list(accumulate(stats.get("lastHitsPerMinute") or []))
    cumulative_hero_damage = list(accumulate(stats.get("heroDamagePerMinute") or []))
    cumulative_tower_damage = list(accumulate(stats.get("towerDamagePerMinute") or []))

    return MatchTimings(
        match_id=match_id,
        hero_id=player["heroId"],
        item_timings=item_timings,
        networth_per_min=stats.get("networthPerMinute") or [],
        cumulative_last_hits=cumulative_last_hits,
        cumulative_hero_damage=cumulative_hero_damage,
        cumulative_tower_damage=cumulative_tower_damage,
        level_timings=level_timings,
        account_id=account_id,
        player_name=player_name,
        position=player.get("position"),
        is_victory=player.get("isVictory"),
        duration_seconds=duration_seconds,
    )
