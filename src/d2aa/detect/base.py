"""Detector abstraction.

This is the seam that lets the Linux-only netcon detector drop in later without
touching the app loop. Every detector exposes the same ``start()/poll()/stop()``
shape; the loop calls ``poll()`` and reacts to a returned ``MatchEvent`` without
knowing or caring how it was produced (screen pixels vs. console stream).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class MatchEvent:
    kind: str = "match_found"  # extensible: e.g. "match_accepted" later
    confidence: float = 1.0


class Detector(ABC):
    @abstractmethod
    def start(self) -> None:
        """Prepare for polling (open sockets, start capture, ...)."""

    @abstractmethod
    def poll(self) -> MatchEvent | None:
        """Non-blocking check. Return a ``MatchEvent`` or ``None``."""

    @abstractmethod
    def stop(self) -> None:
        """Release resources. Safe to call more than once."""
