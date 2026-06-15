"""Tests for constants loading, including item costs."""

from __future__ import annotations

from typing import Any

from d2kit.stats.stratz import constants

_PAYLOAD = {
    "constants": {
        "items": [
            {"id": 1, "shortName": "blink", "stat": {"cost": 2250}},
            {"id": 2, "shortName": "tango", "stat": {"cost": 90}},
            {"id": 3, "shortName": "weird", "stat": None},  # null stat → cost 0
        ],
        "heroes": [{"id": 8, "shortName": "jugg", "displayName": "Juggernaut"}],
    }
}


class _FakeClient:
    def query(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        return _PAYLOAD


def test_load_constants_parses_costs(monkeypatch) -> None:
    # Bypass the on-disk TTL cache so the test is hermetic.
    monkeypatch.setattr(constants.cache, "get", lambda *a, **k: None)
    monkeypatch.setattr(constants.cache, "put", lambda *a, **k: None)

    consts = constants.load_constants(_FakeClient())  # type: ignore[arg-type]
    assert consts.item_names[1] == "blink"
    assert consts.item_costs[1] == 2250
    assert consts.item_costs[3] == 0  # null stat handled
    assert consts.cost_by_name["blink"] == 2250
    assert consts.cost_by_name["weird"] == 0
    assert consts.hero_names[8] == "Juggernaut"
