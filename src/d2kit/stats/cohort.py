"""The "pro" benchmark cohort: real pro players' account ids.

Sourced from OpenDota's free ``/proPlayers`` (no token), filtered to accounts
active recently so the benchmark reflects the current patch, and cached for a day.
We use their *ranked pubs* (queried elsewhere), not tournament games.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx

from d2kit.stats import cache

PRO_PLAYERS_URL = "https://api.opendota.com/api/proPlayers"
_TTL = 24 * 3600
_CACHE_KEY = "pro_cohort"


def pro_account_ids(*, active_days: int = 30, limit: int = 80) -> list[int]:
    """Return up to ``limit`` pro account ids active within ``active_days``.

    Most-recently-active first, so a smaller ``limit`` still yields players who
    are currently grinding ranked.
    """
    cached = cache.get(_CACHE_KEY, _TTL)
    if cached is None:
        resp = httpx.get(PRO_PLAYERS_URL, headers={"User-Agent": "d2kit"}, timeout=30.0)
        resp.raise_for_status()
        cached = [
            {"account_id": p["account_id"], "last_match_time": p.get("last_match_time")}
            for p in resp.json()
            if p.get("account_id")
        ]
        cache.put(_CACHE_KEY, cached)

    cutoff = datetime.now(UTC) - timedelta(days=active_days)
    active = [
        p for p in cached if p.get("last_match_time") and _parse(p["last_match_time"]) >= cutoff
    ]
    active.sort(key=lambda p: p["last_match_time"], reverse=True)
    return [p["account_id"] for p in active[:limit]]


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))
