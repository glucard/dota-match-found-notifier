"""Notification backends."""

from __future__ import annotations

from ..config import NtfyConfig
from .base import Notifier
from .ntfy import NtfyNotifier

__all__ = ["Notifier", "NtfyNotifier", "make_notifier"]


def make_notifier(cfg: NtfyConfig) -> Notifier:
    return NtfyNotifier(cfg.server, cfg.topic)
