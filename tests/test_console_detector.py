from __future__ import annotations

from pathlib import Path

from d2aa.detect.base import MatchEvent
from d2aa.detect.console import ConsoleLogDetector, resolve_console_log

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


def test_latches_no_refire(tmp_path):
    p = tmp_path / "console.log"
    p.write_text("")
    det = _started(p)
    with p.open("a") as f:
        f.write("x k_EMsgGCReadyUpStatus 1\n")
    assert det.poll() is not None
    with p.open("a") as f:
        f.write("x k_EMsgGCReadyUpStatus 2\n")  # repeated status line
    assert det.poll() is None  # latched until a new session


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


def test_preflight_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr("sys.platform", "linux")
    det = ConsoleLogDetector(log_path=str(tmp_path / "nope.log"))
    msg = det.preflight()
    assert msg and "condebug" in msg


def test_preflight_windows(monkeypatch):
    monkeypatch.setattr("sys.platform", "win32")
    msg = ConsoleLogDetector().preflight()
    assert msg and "Linux" in msg


def test_resolve_explicit_path(tmp_path):
    p = tmp_path / "console.log"
    p.write_text("")
    assert resolve_console_log(str(p)) == p
    assert resolve_console_log(str(tmp_path / "missing.log")) is None
