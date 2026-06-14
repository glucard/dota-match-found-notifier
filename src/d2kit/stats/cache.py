"""Tiny TTL JSON cache in the user cache dir.

Used for slow-changing data: the item/hero constants and the pro-account cohort.
Benchmarks are recomputed per run (they're a handful of fast calls).
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from platformdirs import user_cache_path

APP_NAME = "d2kit"


def _path(key: str) -> Path:
    return user_cache_path(APP_NAME, appauthor=False) / f"{key}.json"


def get(key: str, ttl_seconds: float) -> Any | None:
    """Return cached value for ``key`` if present and younger than ``ttl_seconds``."""
    path = _path(key)
    if not path.exists():
        return None
    if time.time() - path.stat().st_mtime > ttl_seconds:
        return None
    with path.open() as fh:
        return json.load(fh)


def put(key: str, value: Any) -> None:
    path = _path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as fh:
        json.dump(value, fh)
