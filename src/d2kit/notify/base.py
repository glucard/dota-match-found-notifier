"""Notifier abstraction — anything that can push a message to the user."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Notifier(Protocol):
    def send(
        self,
        *,
        title: str,
        message: str,
        priority: int = 5,
        tags: list[str] | None = None,
        click: str | None = None,
    ) -> None:
        """Deliver a notification. Should not raise on transient failures."""
