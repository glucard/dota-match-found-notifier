"""Tests for the batched pro-cohort fetch and its aliased query builder."""

from __future__ import annotations

import pytest

from d2kit.stats import benchmark
from d2kit.stats.stratz import queries

ITEM_NAMES = {1: "blink"}


def _player(match_id: int, account_id: int | None = None, name: str | None = None) -> dict:
    return {
        "steamAccount": {"id": account_id, "name": name},
        "matches": [
            {
                "id": match_id,
                "durationSeconds": 2000,
                "players": [
                    {
                        "heroId": 8,
                        "position": "POSITION_1",
                        "isVictory": True,
                        "stats": {
                            "itemPurchases": [{"itemId": 1, "time": 600}],
                            "networthPerMinute": [0, 100],
                            "lastHitsPerMinute": [0, 5],
                            "heroDamagePerMinute": [0, 200],
                            "towerDamagePerMinute": [0, 50],
                        },
                        "playbackData": {"abilityLearnEvents": [{"time": 30}]},
                    }
                ],
            }
        ],
    }


def test_build_cohort_query_aliases_each_account_and_rejects_non_int() -> None:
    q = queries.build_cohort_query([111, 222])
    assert "p0: player(steamAccountId: 111)" in q
    assert "p1: player(steamAccountId: 222)" in q
    assert "fragment Timings" in q and "...Timings" in q
    with pytest.raises(ValueError):
        queries.build_cohort_query(["1; drop"])  # type: ignore[list-item]  # ids must be ints


class _FakeClient:
    """Records each query call and replays one aliased payload per batch."""

    def __init__(self) -> None:
        self.calls: list[list[int]] = []
        self._next_match_id = 1000

    def query(self, query_str: str, variables: dict) -> dict:
        # Recover which account ids this batch asked for, in order.
        ids = [
            int(line.split("steamAccountId: ")[1].split(")")[0])
            for line in query_str.splitlines()
            if line.strip().startswith("p") and "player(steamAccountId" in line
        ]
        self.calls.append(ids)
        out = {}
        for i, aid in enumerate(ids):
            out[f"p{i}"] = _player(self._next_match_id, account_id=aid, name=f"pro{aid}")
            self._next_match_id += 1
        return out


def test_fetch_pro_cohort_batches_and_stops_at_target() -> None:
    client = _FakeClient()
    account_ids = list(range(20))  # 20 accounts, each yields 1 match
    result = benchmark.fetch_pro_cohort(
        client,  # type: ignore[arg-type]
        hero_id=8,
        item_names=ITEM_NAMES,
        account_ids=account_ids,
        target=10,
        chunk=8,
    )
    assert len(result) == 10  # trimmed to target
    # 8 + 8 = 16 >= target after two batches; the third chunk is never fetched.
    assert client.calls == [list(range(8)), list(range(8, 16))]


def test_fetch_pro_cohort_tolerates_null_aliases() -> None:
    client = _FakeClient()

    def query_with_gap(query_str: str, variables: dict) -> dict:
        data = _FakeClient.query(client, query_str, variables)
        data["p0"] = None  # an account STRATZ knows nothing about
        return data

    client.query = query_with_gap  # type: ignore[method-assign]
    result = benchmark.fetch_pro_cohort(
        client,  # type: ignore[arg-type]
        hero_id=8,
        item_names=ITEM_NAMES,
        account_ids=[1, 2, 3],
        target=25,
        chunk=8,
    )
    assert len(result) == 2  # the two non-null aliases


def test_fetch_pro_cohort_stamps_provenance() -> None:
    client = _FakeClient()
    result = benchmark.fetch_pro_cohort(
        client,  # type: ignore[arg-type]
        hero_id=8,
        item_names=ITEM_NAMES,
        account_ids=[42],
        target=5,
        chunk=8,
    )
    assert result[0].account_id == 42
    assert result[0].player_name == "pro42"
    assert result[0].position == "POSITION_1"
    assert result[0].is_victory is True
    assert result[0].duration_seconds == 2000


def test_aggregate_reports_sample_counts() -> None:
    from d2kit.stats.timings import extract_timings

    a = extract_timings(1, _player(1)["matches"][0]["players"][0], ITEM_NAMES)
    b = extract_timings(2, _player(2)["matches"][0]["players"][0], ITEM_NAMES)
    agg = benchmark.aggregate([a, b])
    assert agg.item_counts["blink"] == 2  # both bought it
    assert agg.last_hits_n_at(1) == 2  # both reached minute 1
    assert agg.networth_n_at(1) == 2
