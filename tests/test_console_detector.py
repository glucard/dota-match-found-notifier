from __future__ import annotations

from pathlib import Path

from d2kit.detect.base import MatchEvent
from d2kit.detect.console import ConsoleLogDetector, resolve_console_log

_TRIGGER = "06/13 [GCClient] Recv msg 7170 (k_EMsgGCReadyUpStatus), 21 bytes\n"


def _started(path: Path) -> ConsoleLogDetector:
    det = ConsoleLogDetector(log_path=str(path))
    det.start()
    return det


def test_fires_on_trigger_appended(tmp_path):
    p = tmp_path / "console.log"
    p.write_text("boot line\n")
    det = _started(p)
    assert det.poll() is None  # seek-to-end skips pre-existing history
    with p.open("a") as f:
        f.write(_TRIGGER)
    ev = det.poll()
    assert isinstance(ev, MatchEvent)
    assert ev.kind == "match_found"


def test_fires_again_for_a_later_readycheck_same_session(tmp_path):
    # Regression: the detector must fire for EVERY ready-check in a session, not
    # just the first. (Deduping the repeated status lines within one check is the
    # watch loop's cooldown job, not a permanent per-detector latch.)
    p = tmp_path / "console.log"
    p.write_text("")
    det = _started(p)
    with p.open("a") as f:
        f.write("first k_EMsgGCReadyUpStatus\n")
    assert det.poll() is not None
    # ...minutes later, a new match is found in the SAME Dota session...
    with p.open("a") as f:
        f.write("second k_EMsgGCReadyUpStatus\n")
    assert det.poll() is not None  # would fail with the old permanent latch


def test_ignores_non_trigger(tmp_path):
    p = tmp_path / "console.log"
    p.write_text("")
    det = _started(p)
    with p.open("a") as f:
        f.write("06/13 [GCClient] Recv msg 7198 (k_EMsgGCMatchmakingStatsResponse)\n")
    assert det.poll() is None


def test_truncation_resets_and_refires(tmp_path):
    p = tmp_path / "console.log"
    p.write_text("")
    det = _started(p)
    with p.open("a") as f:
        f.write("a k_EMsgGCReadyUpStatus\n")
    assert det.poll() is not None
    p.write_text("")  # -conclearlog truncates on a new Dota session
    assert det.poll() is None  # observe the shrink, reset offset + latch
    with p.open("a") as f:
        f.write("b k_EMsgGCReadyUpStatus\n")
    assert det.poll() is not None  # fires again next session


def test_custom_triggers(tmp_path):
    p = tmp_path / "console.log"
    p.write_text("")
    det = ConsoleLogDetector(log_path=str(p), triggers=["FoundMatch"])
    det.start()
    with p.open("a") as f:
        f.write("k_EMsgGCReadyUpStatus should be ignored now\n")
    assert det.poll() is None
    with p.open("a") as f:
        f.write("...FoundMatch...\n")
    assert det.poll() is not None


def test_preflight_missing_file(tmp_path):
    det = ConsoleLogDetector(log_path=str(tmp_path / "nope.log"))
    msg = det.preflight()
    assert msg and "condebug" in msg


def test_preflight_ok_on_any_platform(tmp_path, monkeypatch):
    # Console detection works on Windows too (console.log is real-time there).
    monkeypatch.setattr("sys.platform", "win32")
    p = tmp_path / "console.log"
    p.write_text("")
    det = ConsoleLogDetector(log_path=str(p))
    assert det.preflight() is None


def test_resolve_explicit_path(tmp_path):
    p = tmp_path / "console.log"
    p.write_text("")
    assert resolve_console_log(str(p)) == p
    assert resolve_console_log(str(tmp_path / "missing.log")) is None


def test_resolve_via_libraryfolders_second_drive(tmp_path, monkeypatch):
    # Steam root with a libraryfolders.vdf that points to a second-drive library
    # where Dota actually lives.
    root = tmp_path / "Steam"
    (root / "steamapps").mkdir(parents=True)
    lib2 = tmp_path / "drive2" / "SteamLibrary"
    dota_dir = lib2 / "steamapps" / "common" / "dota 2 beta" / "game" / "dota"
    dota_dir.mkdir(parents=True)
    (dota_dir / "console.log").write_text("")
    (root / "steamapps" / "libraryfolders.vdf").write_text(
        f'"libraryfolders"\n{{\n  "0" {{ "path" "{root}" }}\n  "1" {{ "path" "{lib2}" }}\n}}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("d2kit.detect.console._STEAM_ROOTS", [str(root)])
    assert resolve_console_log("auto") == dota_dir / "console.log"
