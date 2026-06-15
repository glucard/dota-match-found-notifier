"""Tests for timing extraction, using a payload shaped like real STRATZ data."""

from __future__ import annotations

from d2kit.stats.benchmark import aggregate
from d2kit.stats.timings import extract_timings

ITEM_NAMES = {1: "blink", 34: "magic_stick", 116: "black_king_bar"}

PLAYER = {
    "heroId": 6,
    "stats": {
        "itemPurchases": [
            {"itemId": 34, "time": -90},
            {"itemId": 1, "time": 600},
            {"itemId": 1, "time": 1200},  # later dupe should be ignored
            {"itemId": 999, "time": 300},  # unknown id should be skipped
        ],
        "networthPerMinute": [0, 100, 250, 500],
        "lastHitsPerMinute": [0, 8, 12, 21],  # per-minute gains -> cumulative 0,8,20,41
        "heroDamagePerMinute": [0, 50, 100, 200],  # -> cumulative 0,50,150,350
        "towerDamagePerMinute": [0, 0, 300, 100],  # -> cumulative 0,0,300,400
    },
    "playbackData": {
        "abilityLearnEvents": [{"time": 120}, {"time": 30}, {"time": 300}],
    },
}


def test_extract_keeps_first_purchase_and_skips_unknown() -> None:
    t = extract_timings(8851262131, PLAYER, ITEM_NAMES)
    assert t.item_timings == {"magic_stick": -90, "blink": 600}
    assert "999" not in t.item_timings


def test_level_timings_sorted_by_time() -> None:
    t = extract_timings(1, PLAYER, ITEM_NAMES)
    assert t.level_timings == [30, 120, 300]
    assert t.level_time(2) == 120
    assert t.level_time(99) is None


def test_metric_lookups() -> None:
    t = extract_timings(1, PLAYER, ITEM_NAMES)
    assert t.last_hits_at(2) == 20  # cumulative: 0+8+12
    assert t.last_hits_at(3) == 41  # + 21
    assert t.last_hits_at(10) is None
    assert t.networth_at(2) == 250
    assert t.hero_damage_at(2) == 150  # cumulative: 0+50+100
    assert t.tower_damage_at(3) == 400  # cumulative: 0+0+300+100
    assert t.tower_damage_at(10) is None


def test_extract_populates_provenance_and_context() -> None:
    t = extract_timings(
        5, PLAYER, ITEM_NAMES, account_id=42, player_name="pro", duration_seconds=1800
    )
    assert t.account_id == 42
    assert t.player_name == "pro"
    assert t.duration_seconds == 1800
    assert t.duration_for_gate == 1800


def test_duration_for_gate_falls_back_to_networth_length() -> None:
    t = extract_timings(5, PLAYER, ITEM_NAMES)  # no duration → 4 net-worth minutes
    assert t.duration_seconds is None
    assert t.duration_for_gate == 4 * 60


def test_significant_items_filters_by_cost() -> None:
    t = extract_timings(5, PLAYER, ITEM_NAMES)
    cost_by_name = {"blink": 2250, "magic_stick": 200}
    assert t.significant_items(cost_by_name, 1000) == frozenset({"blink"})


def test_aggregate_uses_median() -> None:
    a = extract_timings(1, PLAYER, ITEM_NAMES)
    b = extract_timings(2, PLAYER, ITEM_NAMES)
    agg = aggregate([a, b])
    assert agg.sample_size == 2
    assert agg.item_medians["blink"] == 600
    assert agg.last_hits_at(3) == 41
    assert agg.level_time(1) == 30
