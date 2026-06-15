"""Item / hero id<->name constants, fetched from STRATZ and cached for a day."""

from __future__ import annotations

from dataclasses import dataclass

from d2kit.stats import cache
from d2kit.stats.stratz import queries
from d2kit.stats.stratz.client import StratzClient

_TTL = 24 * 3600
# v2: payload now carries item costs; bump so a stale v1 blob isn't read without them.
_CACHE_KEY = "constants_v2"


@dataclass(frozen=True)
class Constants:
    item_names: dict[int, str]  # itemId -> shortName, e.g. 1 -> "blink"
    hero_names: dict[int, str]  # heroId -> displayName, e.g. 6 -> "Drow Ranger"
    item_costs: dict[int, int]  # itemId -> gold cost, e.g. 1 -> 2250
    cost_by_name: dict[str, int]  # shortName -> gold cost (derived, for build filtering)

    def hero_id_by_name(self, name: str) -> int | None:
        """Case-insensitive lookup of a hero id by display name."""
        target = name.strip().lower()
        for hid, hname in self.hero_names.items():
            if hname.lower() == target:
                return hid
        return None


def load_constants(client: StratzClient) -> Constants:
    cached = cache.get(_CACHE_KEY, _TTL)
    if cached is None:
        data = client.query(queries.CONSTANTS)
        cached = {
            "items": {str(i["id"]): i["shortName"] for i in data["constants"]["items"]},
            "heroes": {str(h["id"]): h["displayName"] for h in data["constants"]["heroes"]},
            # stat or cost can be null for some items; default to 0 (treated insignificant).
            "item_costs": {
                str(i["id"]): ((i.get("stat") or {}).get("cost") or 0)
                for i in data["constants"]["items"]
            },
        }
        cache.put(_CACHE_KEY, cached)
    item_names = {int(k): v for k, v in cached["items"].items()}
    hero_names = {int(k): v for k, v in cached["heroes"].items()}
    item_costs = {int(k): int(v) for k, v in cached["item_costs"].items()}
    cost_by_name = {item_names[i]: c for i, c in item_costs.items() if i in item_names}
    return Constants(
        item_names=item_names,
        hero_names=hero_names,
        item_costs=item_costs,
        cost_by_name=cost_by_name,
    )
