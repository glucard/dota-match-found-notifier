"""Tests for duration-gated build divergence."""

from __future__ import annotations

from d2kit.stats.divergence import compute_divergence
from d2kit.stats.timings import MatchTimings

COSTS = {"bfury": 4000, "manta": 4600, "satanic": 5000, "butterfly": 5500, "magic_stick": 200}


def _mt(
    match_id: int,
    items: dict[str, int],
    *,
    duration: int = 2400,  # 40 min default
) -> MatchTimings:
    return MatchTimings(
        match_id=match_id,
        hero_id=8,
        item_timings=items,
        networth_per_min=[],
        cumulative_last_hits=[],
        cumulative_hero_damage=[],
        cumulative_tower_damage=[],
        level_timings=[],
        duration_seconds=duration,
    )


def test_missing_flags_common_item_within_game_length() -> None:
    analyzed = _mt(0, {"bfury": 700}, duration=2400)  # 40-min game, no manta
    pool = [_mt(i, {"bfury": 650, "manta": 1200}, duration=2400) for i in range(1, 6)]
    div = compute_divergence(analyzed, pool, COSTS)
    assert [d.item for d in div.missing] == ["manta"]
    assert div.missing[0].pct == 1.0
    assert div.missing[0].n == 5


def test_missing_not_flagged_when_pros_bought_it_after_your_game_ended() -> None:
    analyzed = _mt(0, {"bfury": 700}, duration=1200)  # short 20-min game
    # Pros all bought satanic, but at ~35 min — after your game ended.
    pool = [_mt(i, {"bfury": 650, "satanic": 2100}, duration=2400) for i in range(1, 6)]
    div = compute_divergence(analyzed, pool, COSTS)
    assert div.missing == []  # duration gate suppresses it


def test_unusual_flags_your_rare_item_when_pros_had_time() -> None:
    analyzed = _mt(0, {"bfury": 700, "manta": 1300}, duration=2400)
    # Pros rarely build manta, and their games run long enough to have bought it.
    pool = [_mt(i, {"bfury": 650}, duration=2400) for i in range(1, 6)]
    div = compute_divergence(analyzed, pool, COSTS)
    assert [d.item for d in div.unusual] == ["manta"]
    assert div.unusual[0].pct == 0.0


def test_cheap_items_never_appear() -> None:
    analyzed = _mt(0, {"bfury": 700}, duration=2400)
    pool = [_mt(i, {"bfury": 650, "magic_stick": 120}, duration=2400) for i in range(1, 6)]
    div = compute_divergence(analyzed, pool, COSTS)
    assert all(d.item != "magic_stick" for d in div.missing)


def test_empty_pool() -> None:
    div = compute_divergence(_mt(0, {"bfury": 700}), [], COSTS)
    assert div.pool_size == 0
    assert div.missing == [] and div.unusual == []
