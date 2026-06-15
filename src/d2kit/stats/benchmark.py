"""Fetch match sets and aggregate them into benchmark medians.

Two benchmarks share this machinery:
  * **personal** — your last-N ranked matches on a hero (one API call)
  * **pro-pub** — recent parsed ranked pubs across a cohort of pro accounts
    (batched via aliased GraphQL: a few accounts per call until the target sample)

Medians (not means) so a single skipped item or stomped/fed game doesn't skew
the benchmark.
"""

from __future__ import annotations

from statistics import median
from typing import Any

from pydantic import BaseModel

from d2kit.stats.stratz import queries
from d2kit.stats.stratz.client import StratzClient
from d2kit.stats.timings import MatchTimings, extract_timings


class Aggregate(BaseModel):
    """Median timings across a set of matches, with per-metric sample counts.

    The ``*_counts`` mirror the medians position-for-position: how many matches
    actually contributed to each item / minute / level, so the renderer can show
    sample size and dim low-confidence deltas.
    """

    sample_size: int
    item_medians: dict[str, float]  # item shortName -> median first-purchase second
    item_counts: dict[str, int]  # item shortName -> how many matches bought it
    networth_per_min: list[float]  # index = minute -> median net worth
    networth_counts: list[int]
    last_hits_per_min: list[float]  # index = minute -> median cumulative last hits
    last_hits_counts: list[int]
    hero_damage_per_min: list[float]  # index = minute -> median cumulative hero damage
    hero_damage_counts: list[int]
    tower_damage_per_min: list[float]  # index = minute -> median cumulative structure damage
    tower_damage_counts: list[int]
    level_medians: list[float]  # index i -> median seconds to reach level i+1
    level_counts: list[int]

    def last_hits_at(self, minute: int) -> float | None:
        return self.last_hits_per_min[minute] if minute < len(self.last_hits_per_min) else None

    def last_hits_n_at(self, minute: int) -> int:
        return self.last_hits_counts[minute] if minute < len(self.last_hits_counts) else 0

    def networth_at(self, minute: int) -> float | None:
        return self.networth_per_min[minute] if minute < len(self.networth_per_min) else None

    def networth_n_at(self, minute: int) -> int:
        return self.networth_counts[minute] if minute < len(self.networth_counts) else 0

    def hero_damage_at(self, minute: int) -> float | None:
        return self.hero_damage_per_min[minute] if minute < len(self.hero_damage_per_min) else None

    def hero_damage_n_at(self, minute: int) -> int:
        return self.hero_damage_counts[minute] if minute < len(self.hero_damage_counts) else 0

    def tower_damage_at(self, minute: int) -> float | None:
        return (
            self.tower_damage_per_min[minute] if minute < len(self.tower_damage_per_min) else None
        )

    def tower_damage_n_at(self, minute: int) -> int:
        return self.tower_damage_counts[minute] if minute < len(self.tower_damage_counts) else 0

    def level_time(self, level: int) -> float | None:
        idx = level - 1
        return self.level_medians[idx] if 0 <= idx < len(self.level_medians) else None

    def level_n(self, level: int) -> int:
        idx = level - 1
        return self.level_counts[idx] if 0 <= idx < len(self.level_counts) else 0


def _column_medians_counts(series: list[list[int]]) -> tuple[list[float], list[int]]:
    """Position-wise median + sample count across ragged lists.

    Each minute/level uses only the matches long enough to have a value there, so
    the returned counts taper off as fewer games reach later positions.
    """
    if not series:
        return [], []
    longest = max(len(s) for s in series)
    medians: list[float] = []
    counts: list[int] = []
    for i in range(longest):
        col = [s[i] for s in series if i < len(s)]
        if col:
            medians.append(median(col))
            counts.append(len(col))
    return medians, counts


def aggregate(matches: list[MatchTimings]) -> Aggregate:
    by_item: dict[str, list[int]] = {}
    for m in matches:
        for item, time in m.item_timings.items():
            by_item.setdefault(item, []).append(time)
    nw_med, nw_cnt = _column_medians_counts([m.networth_per_min for m in matches])
    lh_med, lh_cnt = _column_medians_counts([m.cumulative_last_hits for m in matches])
    hd_med, hd_cnt = _column_medians_counts([m.cumulative_hero_damage for m in matches])
    td_med, td_cnt = _column_medians_counts([m.cumulative_tower_damage for m in matches])
    lv_med, lv_cnt = _column_medians_counts([m.level_timings for m in matches])
    return Aggregate(
        sample_size=len(matches),
        item_medians={item: median(times) for item, times in by_item.items()},
        item_counts={item: len(times) for item, times in by_item.items()},
        networth_per_min=nw_med,
        networth_counts=nw_cnt,
        last_hits_per_min=lh_med,
        last_hits_counts=lh_cnt,
        hero_damage_per_min=hd_med,
        hero_damage_counts=hd_cnt,
        tower_damage_per_min=td_med,
        tower_damage_counts=td_cnt,
        level_medians=lv_med,
        level_counts=lv_cnt,
    )


def _matches_from_payload(
    payload: dict[str, Any], item_names: dict[int, str]
) -> list[MatchTimings]:
    # The cohort query carries id/name here; the personal query only isAnonymous (→ None).
    steam_account = payload.get("steamAccount") or {}
    account_id = steam_account.get("id")
    player_name = steam_account.get("name")
    out: list[MatchTimings] = []
    for m in payload.get("matches") or []:
        players = m.get("players") or []
        if not players:
            continue
        out.append(
            extract_timings(
                m["id"],
                players[0],
                item_names,
                account_id=account_id,
                player_name=player_name,
                duration_seconds=m.get("durationSeconds"),
            )
        )
    return out


def fetch_personal(
    client: StratzClient, account_id: int, hero_id: int, item_names: dict[int, str], take: int
) -> list[MatchTimings]:
    """Your last ``take`` ranked matches on ``hero_id`` (single API call)."""
    data = client.query(
        queries.PLAYER_HERO_MATCHES, {"id": account_id, "hero": hero_id, "take": take}
    )
    return _matches_from_payload(data["player"], item_names)


def fetch_pro_cohort(
    client: StratzClient,
    hero_id: int,
    item_names: dict[int, str],
    account_ids: list[int],
    *,
    target: int = 80,
    per_pro: int = 3,
    chunk: int = 8,
) -> list[MatchTimings]:
    """Recent ranked pubs on ``hero_id`` across the cohort, until ``target`` reached.

    Accounts are queried ``chunk`` at a time in a single aliased GraphQL request
    (``chunk`` kept under STRATZ's ~10-account complexity ceiling), so the whole
    cohort costs a handful of calls instead of one per account. Stops early once
    enough samples are collected. ``target`` is deliberately high: downstream
    position + build-similarity filtering discards most of these, so the raw pool
    must be large for the filtered pool to stay usable.
    """
    collected: list[MatchTimings] = []
    for start in range(0, len(account_ids), chunk):
        if len(collected) >= target:
            break
        batch = account_ids[start : start + chunk]
        data = client.query(queries.build_cohort_query(batch), {"hero": hero_id, "take": per_pro})
        for player in data.values():  # one aliased entry (p0, p1, …) per account
            if player:
                collected.extend(_matches_from_payload(player, item_names))
    return collected[:target]


def fetch_match(
    client: StratzClient, match_id: int, account_id: int, item_names: dict[int, str]
) -> MatchTimings | None:
    """Timings for ``account_id`` in one specific match."""
    data = client.query(queries.MATCH_PLAYER_TIMINGS, {"id": match_id, "account": account_id})
    match = data.get("match") or {}
    players = match.get("players") or []
    if not players:
        return None
    return extract_timings(
        match_id, players[0], item_names, duration_seconds=match.get("durationSeconds")
    )
