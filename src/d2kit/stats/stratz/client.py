"""STRATZ GraphQL client.

Thin synchronous wrapper over the STRATZ GraphQL endpoint. STRATZ requires a
Bearer token and rejects default/empty User-Agents, so we always send
``User-Agent: STRATZ_API``.
"""

from __future__ import annotations

from typing import Any

import httpx

ENDPOINT = "https://api.stratz.com/graphql"


class StratzError(RuntimeError):
    """Raised when STRATZ returns an HTTP error or a GraphQL ``errors`` payload."""


class StratzClient:
    """Minimal GraphQL client for STRATZ.

    Usage::

        with StratzClient(token) as client:
            data = client.query(queries.CONSTANTS)
    """

    def __init__(self, token: str, *, timeout: float = 30.0) -> None:
        self._client = httpx.Client(
            headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": "STRATZ_API",
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )

    def query(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute a GraphQL query and return its ``data`` object."""
        resp = self._client.post(ENDPOINT, json={"query": query, "variables": variables or {}})
        if resp.status_code >= 400:
            raise StratzError(f"HTTP {resp.status_code}: {resp.text[:500]}")
        payload = resp.json()
        if payload.get("errors"):
            raise StratzError(f"GraphQL errors: {payload['errors']}")
        data: dict[str, Any] = payload["data"]
        return data

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> StratzClient:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()
