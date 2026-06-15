"""Tests for role + build-similarity pool selection."""

from __future__ import annotations

from d2kit.stats import similarity
from d2kit.stats.timings import MatchTimings

COSTS = {
    "blink": 2250,
    "bfury": 4000,
    "manta": 4600,
    "butterfly": 5500,
    "treads": 1400,
    "satanic": 5000,
    "magic_stick": 200,  # below threshold → ignored
}


def _mt(
    match_id: int,
    items: dict[str, int],
    *,
    position: str | None = "POSITION_1",
    account_id: int | None = None,
    name: str | None = None,
    victory: bool | None = None,
) -> MatchTimings:
    return MatchTimings(
        match_id=match_id,
        hero_id=8,
        item_timings=items,
        networth_per_min=[0, 100],
        cumulative_last_hits=[0, 5],
        cumulative_hero_damage=[],
        cumulative_tower_damage=[],
        level_timings=[30],
        account_id=account_id,
        player_name=name,
        position=position,
        is_victory=victory,
    )


def test_overlap_and_jaccard() -> None:
    a = frozenset({"bfury", "manta"})
    sup = frozenset({"bfury", "manta", "butterfly", "satanic"})
    assert similarity.overlap_coefficient(a, sup) == 1.0  # subset → perfect
    assert similarity.jaccard(a, sup) == 0.5
    assert similarity.overlap_coefficient(a, frozenset()) == 0.0
    assert similarity.overlap_coefficient(a, frozenset({"blink"})) == 0.0


def test_position_gate() -> None:
    pool = [
        _mt(1, {"bfury": 600}, position="POSITION_1"),
        _mt(2, {"bfury": 600}, position="POSITION_2"),
    ]
    kept = similarity.filter_by_position(pool, "POSITION_1")
    assert [m.match_id for m in kept] == [1]
    assert len(similarity.filter_by_position(pool, None)) == 2


def test_strict_mode_and_subset_match() -> None:
    analyzed = _mt(0, {"bfury": 700, "manta": 1300})  # short game, 2 core items
    # Six pros with the same core plus extra late items (longer games).
    pool = [
        _mt(i, {"bfury": 650, "manta": 1250, "butterfly": 2200}, account_id=i, name=f"p{i}")
        for i in range(1, 7)
    ]
    sel = similarity.select_similar(analyzed, pool, COSTS)
    assert sel.mode == "strict"
    assert len(sel.matches) == 6
    assert sel.distinct_players == 6


def test_unfiltered_when_no_significant_items() -> None:
    analyzed = _mt(0, {"magic_stick": 200})  # nothing ≥ threshold
    pool = [_mt(i, {"bfury": 600}, account_id=i) for i in range(1, 4)]
    sel = similarity.select_similar(analyzed, pool, COSTS)
    assert sel.mode == "unfiltered"
    assert len(sel.matches) == 3


def test_top_n_fallback_picks_most_similar() -> None:
    analyzed = _mt(0, {"bfury": 700, "manta": 1300, "butterfly": 2000})
    # No build is close enough for relaxed; pick the most-similar min_pool.
    pool = [_mt(i, {"blink": 600, "satanic": 1200}, account_id=i) for i in range(1, 4)]
    pool.append(_mt(99, {"bfury": 650, "manta": 1250}, account_id=99))  # most similar
    sel = similarity.select_similar(analyzed, pool, COSTS, min_pool=2)
    assert sel.mode == "top_n"
    assert len(sel.matches) == 2
    assert sel.matches[0].match_id == 99  # ranked first by overlap


def test_win_rate_and_contributors() -> None:
    analyzed = _mt(0, {"bfury": 700, "manta": 1300})
    pool = [
        _mt(1, {"bfury": 650, "manta": 1250}, account_id=1, name="alice", victory=True),
        _mt(2, {"bfury": 650, "manta": 1250}, account_id=1, name="alice", victory=False),
        _mt(3, {"bfury": 650, "manta": 1250}, account_id=2, name="bob", victory=True),
        _mt(4, {"bfury": 650, "manta": 1250}, account_id=2, name="bob", victory=True),
        _mt(5, {"bfury": 650, "manta": 1250}, account_id=3, name="cara", victory=True),
    ]
    sel = similarity.select_similar(analyzed, pool, COSTS)
    assert sel.win_rate == 0.8  # 4 of 5
    assert sel.distinct_players == 3
    assert ("alice", 2) in sel.top_contributors


def test_anonymous_contributor_falls_back_to_account_id() -> None:
    analyzed = _mt(0, {"bfury": 700, "manta": 1300})
    pool = [_mt(i, {"bfury": 650, "manta": 1250}, account_id=777, name=None) for i in range(1, 6)]
    sel = similarity.select_similar(analyzed, pool, COSTS)
    assert sel.top_contributors == [("777", 5)]
