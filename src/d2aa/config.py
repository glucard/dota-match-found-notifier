"""Config schema plus TOML load/save.

The on-disk format is documented in the README; this module is the single source
of truth for defaults and (de)serialization. Reading uses stdlib ``tomllib``;
writing uses ``tomli_w`` (stdlib has no TOML writer).
"""

from __future__ import annotations

import secrets
import tomllib
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

import tomli_w

from .paths import config_file


class ConfigError(Exception):
    """Raised when the config is missing or structurally invalid."""


@dataclass
class DetectorConfig:
    backend: str = "pixel"  # "pixel" | "netcon" (future)
    # netcon settings are ignored by the pixel backend but kept so the file is
    # ready for the Linux-only netcon detector dropping in later.
    netcon_port: int = 28000


@dataclass
class CaptureConfig:
    backend: str = "auto"  # "auto" | "mss" | "pipewire"
    restore_token: str = ""  # PipeWire portal one-time-consent token (Wayland)


@dataclass
class NtfyConfig:
    server: str = "https://ntfy.sh"
    topic: str = ""  # generated on first config if empty
    priority: int = 5
    tags: list[str] = field(default_factory=lambda: ["video_game", "rotating_light"])
    click: str = ""  # optional URL opened when the notification is tapped


@dataclass
class Calibration:
    # Fractional screen coordinates (0..1) so calibration survives a resolution
    # change. ``color`` is the sampled Accept-button RGB. Detection counts, within
    # a ``region`` x ``region`` box around (x, y), the fraction of pixels whose RGB
    # is within ``tolerance`` (Euclidean) of ``color``; it fires when that fraction
    # reaches ``min_fraction``. ``patch`` is the NxN patch averaged when sampling
    # the target color during calibration.
    x: float = 0.5
    y: float = 0.72
    color: list[int] = field(default_factory=lambda: [108, 168, 50])  # Dota Accept green
    tolerance: float = 40.0
    region: int = 28
    min_fraction: float = 0.40
    patch: int = 5
    calibrated: bool = False


@dataclass
class RuntimeConfig:
    poll_interval: float = 0.25  # seconds between detector polls
    cooldown: float = 30.0  # seconds to suppress repeat notifications
    confirm_frames: int = 3  # consecutive positive polls required before firing


@dataclass
class Config:
    detector: DetectorConfig = field(default_factory=DetectorConfig)
    capture: CaptureConfig = field(default_factory=CaptureConfig)
    ntfy: NtfyConfig = field(default_factory=NtfyConfig)
    calibration: Calibration = field(default_factory=Calibration)
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)

    # -- serialization -----------------------------------------------------

    def to_toml_dict(self) -> dict[str, Any]:
        """Nested dict matching the documented TOML layout."""
        return {
            "detector": {
                "backend": self.detector.backend,
                "netcon": {"port": self.detector.netcon_port},
            },
            "capture": asdict(self.capture),
            "ntfy": asdict(self.ntfy),
            "calibration": asdict(self.calibration),
            "runtime": asdict(self.runtime),
        }

    @classmethod
    def from_toml_dict(cls, data: dict[str, Any]) -> Config:
        det = data.get("detector", {})
        cfg = cls(
            detector=DetectorConfig(
                backend=det.get("backend", "pixel"),
                netcon_port=det.get("netcon", {}).get("port", 28000),
            ),
            capture=_build(CaptureConfig, data.get("capture", {})),
            ntfy=_build(NtfyConfig, data.get("ntfy", {})),
            calibration=_build(Calibration, data.get("calibration", {})),
            runtime=_build(RuntimeConfig, data.get("runtime", {})),
        )
        return cfg


def _build(cls: type, data: dict[str, Any]):
    """Construct a dataclass from a dict, ignoring unknown keys."""
    known = {f.name for f in fields(cls)}
    return cls(**{k: v for k, v in data.items() if k in known})


def new_topic() -> str:
    """A hard-to-guess default ntfy topic (acts as the shared secret)."""
    return f"d2aa-{secrets.token_urlsafe(9)}"


def load(path: Path | None = None) -> Config:
    """Load config from disk, raising a friendly error if absent/unusable."""
    path = path or config_file()
    if not path.exists():
        raise ConfigError(f"No config found at {path}.\nRun  d2aa --config  to set it up first.")
    try:
        with path.open("rb") as fh:
            data = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"Could not read config at {path}: {exc}") from exc
    return Config.from_toml_dict(data)


def save(cfg: Config, path: Path | None = None) -> Path:
    """Write config to disk, returning the path written."""
    path = path or config_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as fh:
        tomli_w.dump(cfg.to_toml_dict(), fh)
    return path
