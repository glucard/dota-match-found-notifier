"""Fetch match sets and aggregate them into benchmark medians.

Two benchmarks share this machinery:
  * **personal** — your last-N ranked matches on a hero (one API call)
  * **pro-pub** — recent parsed ranked pubs across a cohort of pro accounts
    (one call per pro until we reach the target sample)

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
    """Median timings across a set of matches."""

    sample_size: int
    item_medians: dict[str, float]  # item shortName -> median first-purchase second
    networth_per_min: list[float]  # index = minute -> median net worth
    last_hits_per_min: list[float]  # index = minute -> median cumulative last hits
    level_medians: list[float]  # index i -> median seconds to reach level i+1

    def last_hits_at(self, minute: int) -> float | None:
        return self.last_hits_per_min[minute] if minute < len(self.last_hits_per_min) else None

    def networth_at(self, minute: int) -> float | None:
        return self.networth_per_min[minute] if minute < len(self.networth_per_min) else None

    def level_time(self, level: int) -> float | None:
        idx = level - 1
        return self.level_medians[idx] if 0 <= idx < len(self.level_medians) else None


def _column_medians(series: list[list[int]]) -> list[float]:
    """Position-wise median across ragged lists (uses each minute's available samples)."""
    if not series:
        return []
    longest = max(len(s) for s in series)
    out: list[float] = []
    for i in range(longest):
        col = [s[i] for s in series if i < len(s)]
        if col:
            out.append(median(col))
    return out


def aggregate(matches: list[MatchTimings]) -> Aggregate:
    by_item: dict[str, list[int]] = {}
    for m in matches:
        for item, time in m.item_timings.items():
            by_item.setdefault(item, []).append(time)
    return Aggregate(
        sample_size=len(matches),
        item_medians={item: median(times) for item, times in by_item.items()},
        networth_per_min=_column_medians([m.networth_per_min for m in matches]),
        last_hits_per_min=_column_medians([m.cumulative_last_hits for m in matches]),
        level_medians=_column_medians([m.level_timings for m in matches]),
    )


def _matches_from_payload(
    payload: dict[str, Any], item_names: dict[int, str]
) -> list[MatchTimings]:
    out: list[MatchTimings] = []
    for m in payload.get("matches") or []:
        players = m.get("players") or []
        if not players:
            continue
        out.append(extract_timings(m["id"], players[0], item_names))
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
    target: int = 25,
    per_pro: int = 3,
) -> list[MatchTimings]:
    """Recent ranked pubs on ``hero_id`` across the cohort, until ``target`` reached."""
    collected: list[MatchTimings] = []
    for account_id in account_ids:
        if len(collected) >= target:
            break
        data = client.query(
            queries.PLAYER_HERO_MATCHES, {"id": account_id, "hero": hero_id, "take": per_pro}
        )
        collected.extend(_matches_from_payload(data["player"], item_names))
    return collected[:target]


def fetch_match(
    client: StratzClient, match_id: int, account_id: int, item_names: dict[int, str]
) -> MatchTimings | None:
    """Timings for ``account_id`` in one specific match."""
    data = client.query(queries.MATCH_PLAYER_TIMINGS, {"id": match_id, "account": account_id})
    players = (data.get("match") or {}).get("players") or []
    if not players:
        return None
    return extract_timings(match_id, players[0], item_names)
