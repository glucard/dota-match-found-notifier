from __future__ import annotations

import pytest

from d2kit.config import Config, ConfigError, load, new_topic, save


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
    assert loaded.detector.backend == "pixel"
    assert loaded.detector.console.log_path == "auto"
    assert loaded.detector.console.triggers == ["k_EMsgGCReadyUpStatus"]


def test_legacy_netcon_config_loads(tmp_path):
    # Old configs carried a [detector.netcon] table; it must be ignored cleanly.
    p = tmp_path / "config.toml"
    p.write_text(
        '[detector]\nbackend = "pixel"\n[detector.netcon]\nport = 28000\n',
        encoding="utf-8",
    )
    loaded = load(p)
    assert loaded.detector.backend == "pixel"
    assert loaded.detector.console.log_path == "auto"


def test_missing_file_friendly_error(tmp_path):
    with pytest.raises(ConfigError, match="d2kit --config"):
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
    assert new_topic().startswith("d2kit-")


def test_legacy_migration_imports_both_tools(tmp_path, monkeypatch):
    # Pre-merge: separate ~/.config/d2aa and ~/.config/dota-stats configs.
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    (tmp_path / "d2aa").mkdir()
    (tmp_path / "d2aa" / "config.toml").write_text(
        '[ntfy]\ntopic = "d2aa-old"\n[calibration]\ncalibrated = true\nx = 0.4\n',
        encoding="utf-8",
    )
    (tmp_path / "dota-stats").mkdir()
    (tmp_path / "dota-stats" / "config.toml").write_text(
        'stratz_api_token = "tok123"\naccount_id = 42\nlast_n = 15\n',
        encoding="utf-8",
    )
    loaded = load()  # triggers migrate_legacy() then reads the unified file
    assert loaded.ntfy.topic == "d2aa-old"
    assert loaded.calibration.calibrated is True
    assert loaded.calibration.x == 0.4
    assert loaded.stats.stratz_api_token == "tok123"
    assert loaded.stats.account_id == 42
    assert loaded.stats.last_n == 15
