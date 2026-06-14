"""Unified config (pydantic v2) plus TOML load/save and legacy migration.

One file holds both tools' settings: the match-found notifier (detector / capture /
ntfy / calibration / runtime) and the stats comparison ([stats]). Reading uses
stdlib ``tomllib``; writing uses ``tomli_w``. pydantic gives validation and drops
the hand-rolled serialization. The file is chmod 0600 — it can hold a STRATZ token.
"""

from __future__ import annotations

import os
import secrets
import tomllib
from pathlib import Path

import tomli_w
from platformdirs import user_config_dir
from pydantic import BaseModel, Field

from .paths import config_file


class ConfigError(Exception):
    """Raised when the config is missing or structurally invalid."""


# -- notifier ---------------------------------------------------------------


class ConsoleDetectorConfig(BaseModel):
    log_path: str = "auto"  # "auto" finds Dota's console.log, or an explicit path
    triggers: list[str] = ["k_EMsgGCReadyUpStatus"]


class DetectorConfig(BaseModel):
    backend: str = "pixel"  # "pixel" (screen) | "console" (Game Coordinator log)
    console: ConsoleDetectorConfig = Field(default_factory=ConsoleDetectorConfig)


class CaptureConfig(BaseModel):
    backend: str = "auto"  # "auto" | "mss" | "pipewire"
    restore_token: str = ""  # PipeWire portal one-time-consent token (Wayland)


class NtfyConfig(BaseModel):
    server: str = "https://ntfy.sh"
    topic: str = ""  # generated on first config if empty
    priority: int = 5
    tags: list[str] = ["video_game", "rotating_light"]
    click: str = ""  # optional URL opened when the notification is tapped


class Calibration(BaseModel):
    # Fractional screen coords (0..1) so calibration survives a resolution change.
    # Detection counts, in a ``region`` x ``region`` box around (x, y), the fraction
    # of pixels within ``tolerance`` (RGB Euclidean) of ``color``; fires at
    # ``min_fraction``. ``patch`` is the NxN patch averaged when sampling the color.
    x: float = 0.5
    y: float = 0.72
    color: list[int] = [108, 168, 50]  # Dota Accept green
    tolerance: float = 40.0
    region: int = 28
    min_fraction: float = 0.40
    patch: int = 5
    calibrated: bool = False


class RuntimeConfig(BaseModel):
    poll_interval: float = 0.25  # seconds between detector polls
    cooldown: float = 30.0  # seconds to suppress repeat notifications
    confirm_frames: int = 3  # consecutive positive polls required before firing


# -- stats ------------------------------------------------------------------


class StatsConfig(BaseModel):
    stratz_api_token: str = ""  # STRATZ GraphQL token (held to 0600)
    account_id: int | None = None  # your Steam32 / friend id
    last_n: int = 20  # recent matches forming your personal mean
    filter_turbo: bool = True  # hide Turbo matches from the picker


class Config(BaseModel):
    detector: DetectorConfig = Field(default_factory=DetectorConfig)
    capture: CaptureConfig = Field(default_factory=CaptureConfig)
    ntfy: NtfyConfig = Field(default_factory=NtfyConfig)
    calibration: Calibration = Field(default_factory=Calibration)
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)
    stats: StatsConfig = Field(default_factory=StatsConfig)


def new_topic() -> str:
    """A hard-to-guess default ntfy topic (acts as the shared secret)."""
    return f"d2kit-{secrets.token_urlsafe(9)}"


def resolve_token(cfg: Config) -> str:
    """STRATZ token, with the ``STRATZ_API_TOKEN`` env var taking precedence."""
    return os.environ.get("STRATZ_API_TOKEN") or cfg.stats.stratz_api_token


def load(path: Path | None = None) -> Config:
    """Load config from disk, raising a friendly error if absent/unusable.

    On first run, imports settings from the old separate ``d2aa`` / ``dota-stats``
    config files if present (so nothing has to be re-set-up)."""
    if path is None:
        migrate_legacy()
        path = config_file()
    if not path.exists():
        raise ConfigError(f"No config found at {path}.\nRun  d2kit --config  to set it up first.")
    try:
        with path.open("rb") as fh:
            data = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"Could not read config at {path}: {exc}") from exc
    return Config.model_validate(data)  # extra keys (e.g. legacy [detector.netcon]) ignored


def save(cfg: Config, path: Path | None = None) -> Path:
    """Write config to disk (chmod 0600), returning the path written."""
    path = path or config_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as fh:
        # exclude_none: TOML has no null (e.g. stats.account_id); omit it, the
        # field falls back to its default on load.
        tomli_w.dump(cfg.model_dump(mode="json", exclude_none=True), fh)
    path.chmod(0o600)
    return path


def migrate_legacy() -> None:
    """One-time import of the pre-merge configs into the unified d2kit file."""
    target = config_file()
    if target.exists():
        return
    data: dict = {}
    notifier_old = Path(user_config_dir("d2aa")) / "config.toml"
    if notifier_old.exists():
        with notifier_old.open("rb") as fh:
            data.update(tomllib.load(fh))
    stats_old = Path(user_config_dir("dota-stats")) / "config.toml"
    if stats_old.exists():
        with stats_old.open("rb") as fh:
            data["stats"] = tomllib.load(fh)
    if data:
        save(Config.model_validate(data))
