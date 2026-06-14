from __future__ import annotations

import d2kit.capture as cap
from d2kit.capture import MssCapturer, PipewireCapturer, make_capturer
from d2kit.config import CaptureConfig


def test_forced_mss():
    assert isinstance(make_capturer(CaptureConfig(backend="mss")), MssCapturer)


def test_forced_pipewire():
    assert isinstance(make_capturer(CaptureConfig(backend="pipewire")), PipewireCapturer)


def test_unknown_backend_raises():
    import pytest

    with pytest.raises(cap.CaptureError):
        make_capturer(CaptureConfig(backend="bogus"))


def test_auto_selects_pipewire_on_wayland(monkeypatch):
    monkeypatch.setattr(cap, "is_wayland", lambda: True)
    assert isinstance(make_capturer(CaptureConfig(backend="auto")), PipewireCapturer)


def test_auto_selects_mss_off_wayland(monkeypatch):
    monkeypatch.setattr(cap, "is_wayland", lambda: False)
    assert isinstance(make_capturer(CaptureConfig(backend="auto")), MssCapturer)


def test_is_wayland_reads_env(monkeypatch):
    monkeypatch.setattr(cap.sys, "platform", "linux")
    monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
    assert cap.is_wayland() is True
    monkeypatch.setenv("XDG_SESSION_TYPE", "x11")
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    assert cap.is_wayland() is False
