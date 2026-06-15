"""Duration-gated build divergence: where your build differs from similar pros.

Analytic, not advisory. Over the build+position-similar pro pool it surfaces:

* **missing** — items most similar pros bought *within your game's length* that you
  didn't. The duration gate is the point: an item pros buy at 40 min is never held
  against a 25-min game, so a shorter game never reads as a build mistake.
* **unusual** — items you bought that few similar pros did, but only when their
  games ran long enough that they *could* have bought them too.

Only significant items (cost ≥ threshold) participate, so cheap situational buys
never show up.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Literal

from d2kit.stats.similarity import SIGNIFICANT_COST
from d2kit.stats.timings import MatchTimings

_DEFAULT_MISSING_FLOOR = 0.5
_DEFAULT_UNUSUAL_CEILING = 0.25
_DEFAULT_MAX_ITEMS = 6


@dataclass(frozen=True)
class DivergenceItem:
    item: str  # raw shortName; the renderer titlecases it
    pct: float  # fraction of the similar pool that bought it (0..1)
    n: int  # how many similar matches bought it
    pro_median_time: int | None  # median pro buy-time in seconds (None if nobody bought it)
    direction: Literal["missing", "unusual"]


@dataclass(frozen=True)
class Divergence:
    pool_size: int
    missing: list[DivergenceItem]
    unusual: list[DivergenceItem]


def compute_divergence(
    analyzed: MatchTimings,
    cohort: list[MatchTimings],
    cost_by_name: dict[str, int],
    *,
    threshold_cost: int = SIGNIFICANT_COST,
    missing_floor: float = _DEFAULT_MISSING_FLOOR,
    unusual_ceiling: float = _DEFAULT_UNUSUAL_CEILING,
    max_items: int = _DEFAULT_MAX_ITEMS,
) -> Divergence:
    """Compare ``analyzed``'s build against the similar ``cohort`` (duration-gated)."""
    pool_size = len(cohort)
    if pool_size == 0:
        return Divergence(pool_size=0, missing=[], unusual=[])

    own = analyzed.significant_items(cost_by_name, threshold_cost)
    game_len = analyzed.duration_for_gate

    # Per significant item: the buy-times across the pool that bought it.
    buy_times: dict[str, list[int]] = {}
    for m in cohort:
        for item in m.significant_items(cost_by_name, threshold_cost):
            buy_times.setdefault(item, []).append(m.item_timings[item])

    durations = [m.duration_for_gate for m in cohort]
    pro_median_duration = median(durations) if durations else 0

    missing: list[DivergenceItem] = []
    for item, times in buy_times.items():
        if item in own:
            continue
        pct = len(times) / pool_size
        med = median(times)
        # Gate: pros reliably bought it AND within your game's timeframe.
        if pct >= missing_floor and med <= game_len:
            missing.append(DivergenceItem(item, pct, len(times), int(med), "missing"))
    missing.sort(key=lambda d: d.pct, reverse=True)

    unusual: list[DivergenceItem] = []
    for item in own:
        times = buy_times.get(item, [])
        pct = len(times) / pool_size
        your_buy_time = analyzed.item_timings[item]
        # Gate: pros mostly skipped it AND their games lasted long enough to buy it.
        if pct <= unusual_ceiling and pro_median_duration >= your_buy_time:
            umed = int(median(times)) if times else None
            unusual.append(DivergenceItem(item, pct, len(times), umed, "unusual"))
    unusual.sort(key=lambda d: d.pct)

    return Divergence(pool_size=pool_size, missing=missing[:max_items], unusual=unusual[:max_items])
