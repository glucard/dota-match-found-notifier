from __future__ import annotations

import pytest

from d2aa.config import Config, ConfigError, load, new_topic, save


def test_roundtrip(tmp_path):
    cfg = Config()
    cfg.ntfy.topic = new_topic()
    cfg.calibration.x = 0.42
    cfg.calibration.color = [10, 20, 30]
    cfg.calibration.calibrated = True
    p = tmp_path / "config.toml"
    save(cfg, p)

    loaded = load(p)
    assert loaded.ntfy.topic == cfg.ntfy.topic
    assert loaded.calibration.x == 0.42
    assert loaded.calibration.color == [10, 20, 30]
    assert loaded.calibration.calibrated is True
    assert loaded.detector.netcon_port == 28000  # placeholder survives roundtrip


def test_missing_file_friendly_error(tmp_path):
    with pytest.raises(ConfigError, match="d2aa --config"):
        load(tmp_path / "nope.toml")


def test_unknown_keys_ignored(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text(
        '[ntfy]\ntopic = "x"\nbogus = 1\n[calibration]\nx = 0.1\n',
        encoding="utf-8",
    )
    loaded = load(p)
    assert loaded.ntfy.topic == "x"
    assert loaded.calibration.x == 0.1


def test_defaults():
    cfg = Config()
    assert cfg.detector.backend == "pixel"
    assert cfg.capture.backend == "auto"
    assert cfg.calibration.calibrated is False
    assert new_topic().startswith("d2aa-")
