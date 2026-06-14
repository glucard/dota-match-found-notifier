"""Filesystem locations for d2kit, resolved per-platform via platformdirs."""

from __future__ import annotations

from pathlib import Path

from platformdirs import user_config_dir

_APP = "d2kit"


def config_dir() -> Path:
    """Directory holding ``config.toml`` (created on demand)."""
    path = Path(user_config_dir(_APP))
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_file() -> Path:
    """Absolute path to the user's config file (may not exist yet)."""
    return config_dir() / "config.toml"
