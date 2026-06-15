"""Select the subset of a benchmark pool that resembles the analyzed match.

Two gates, applied in order, so the comparison is apples-to-apples:

1. **Position** — keep only matches played in the analyzed match's role (a pos-1
   safelane carry builds nothing like the same hero played mid).
2. **Build similarity** — keep matches whose *significant-item set* (items costing
   at least ``threshold_cost``) resembles the analyzed match's, scored by the
   **overlap coefficient** ``|U∩P| / min(|U|,|P|)``. Overlap (not Jaccard) is the
   point: it scores 1.0 when one build is a subset of the other, so a short game
   with fewer items still matches a longer game on the same core — exactly the
   "I finished earlier / went longer, same build" case.

A graceful fallback ladder (strict → relaxed → top-N → unfiltered) keeps the pool
usable when few close builds exist, and records which rung it landed on so the UI
can be honest about it.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Literal

from d2kit.stats.timings import MatchTimings

Mode = Literal["strict", "relaxed", "top_n", "unfiltered"]

# A "build item" costs at least this many gold; cheaper buys are situational noise.
SIGNIFICANT_COST = 1000
_DEFAULT_STRICT = 0.6
_DEFAULT_RELAXED = 0.4
_DEFAULT_MIN_POOL = 5
_DEFAULT_MIN_SHARED = 3


def overlap_coefficient(a: frozenset[str], b: frozenset[str]) -> float:
    """``|a∩b| / min(|a|,|b|)`` — 1.0 when one set is a subset of the other."""
    smaller = min(len(a), len(b))
    if smaller == 0:
        return 0.0
    return len(a & b) / smaller


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    """Intersection-over-union — used only as a tie-break (tightest build first)."""
    union = len(a | b)
    if union == 0:
        return 0.0
    return len(a & b) / union


def filter_by_position(pool: list[MatchTimings], position: str | None) -> list[MatchTimings]:
    """Keep matches played in ``position`` (no-op if ``position`` is None)."""
    if position is None:
        return list(pool)
    return [m for m in pool if m.position == position]


@dataclass(frozen=True)
class SimilarSelection:
    """The final compared pool plus how it was chosen, for transparency."""

    matches: list[MatchTimings]
    total_fetched: int  # pool size before any filtering
    position_pool: int  # size after the position gate, before build similarity
    mode: Mode
    distinct_players: int
    top_contributors: list[tuple[str, int]]  # (name-or-id, match_count) desc
    win_rate: float | None  # over the final pool, or None if unknown


def _summarize(
    matches: list[MatchTimings], total_fetched: int, position_pool: int, mode: Mode
) -> SimilarSelection:
    counts: Counter[str] = Counter()
    for m in matches:
        if m.account_id is None:
            continue  # personal pool has no per-player identity
        counts[m.player_name or str(m.account_id)] += 1
    victories = [m.is_victory for m in matches if m.is_victory is not None]
    win_rate = (sum(victories) / len(victories)) if victories else None
    return SimilarSelection(
        matches=matches,
        total_fetched=total_fetched,
        position_pool=position_pool,
        mode=mode,
        distinct_players=len(counts),
        top_contributors=counts.most_common(5),
        win_rate=win_rate,
    )


def select_similar(
    analyzed: MatchTimings,
    pool: list[MatchTimings],
    cost_by_name: dict[str, int],
    *,
    threshold_cost: int = SIGNIFICANT_COST,
    strict: float = _DEFAULT_STRICT,
    relaxed: float = _DEFAULT_RELAXED,
    min_pool: int = _DEFAULT_MIN_POOL,
    min_shared: int = _DEFAULT_MIN_SHARED,
) -> SimilarSelection:
    """Pick the role- and build-similar subset of ``pool`` vs ``analyzed``."""
    total_fetched = len(pool)
    base = filter_by_position(pool, analyzed.position)
    if not base:  # position gate too aggressive — fall back to all positions
        base = list(pool)
    position_pool = len(base)

    own = analyzed.significant_items(cost_by_name, threshold_cost)
    if not own or not base:
        return _summarize(base, total_fetched, position_pool, "unfiltered")

    shared_req = min(min_shared, len(own))
    # (overlap, jaccard, shared_count, match) for each candidate.
    scored: list[tuple[float, float, int, MatchTimings]] = []
    for m in base:
        sig = m.significant_items(cost_by_name, threshold_cost)
        scored.append((overlap_coefficient(own, sig), jaccard(own, sig), len(own & sig), m))

    ladder: tuple[tuple[float, Mode], ...] = ((strict, "strict"), (relaxed, "relaxed"))
    for cutoff, mode in ladder:
        kept = [m for ov, _ja, sh, m in scored if ov >= cutoff and sh >= shared_req]
        if len(kept) >= min_pool:
            return _summarize(kept, total_fetched, position_pool, mode)

    # Top-N fallback: the most-similar handful, even if below the relaxed cutoff.
    scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
    kept = [m for _ov, _ja, _sh, m in scored[:min_pool]]
    return _summarize(kept, total_fetched, position_pool, "top_n")
