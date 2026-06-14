"""ntfy.sh push notifications over plain HTTP.

Publishing is a single POST to ``{server}/{topic}`` with the message as the body
and optional metadata in headers (see https://docs.ntfy.sh/publish/). No auth is
needed for the public server; the topic name is the shared secret.
"""

from __future__ import annotations

import logging

import httpx

log = logging.getLogger(__name__)


def _ascii_header(value: str) -> str:
    """Make a value safe for an HTTP header (which must be ASCII).

    A stray non-ASCII character (e.g. an emoji in a title) would otherwise make
    httpx raise ``UnicodeEncodeError`` and crash the caller. Emoji belong in the
    message body (UTF-8) or in ``tags`` — those render fine; headers don't.
    """
    return value.encode("ascii", "ignore").decode("ascii").strip()


class NtfyNotifier:
    def __init__(self, server: str, topic: str, timeout: float = 5.0) -> None:
        if not topic:
            raise ValueError("ntfy topic is empty; run `d2kit --config` first")
        self._url = f"{server.rstrip('/')}/{topic}"
        # Reuse one connection so a found-match POST skips TCP/TLS setup latency.
        self._client = httpx.Client(timeout=timeout, http2=False)

    def send(
        self,
        *,
        title: str,
        message: str,
        priority: int = 5,
        tags: list[str] | None = None,
        click: str | None = None,
    ) -> None:
        headers: dict[str, str] = {
            "Title": _ascii_header(title),
            "Priority": str(priority),
        }
        if tags:
            headers["Tags"] = _ascii_header(",".join(tags))
        if click:
            headers["Click"] = _ascii_header(click)
        try:
            resp = self._client.post(
                self._url,
                content=message.encode("utf-8"),  # body is UTF-8: emoji/accents OK
                headers=headers,
            )
            resp.raise_for_status()
        except (httpx.HTTPError, UnicodeError) as exc:
            # A failed notification must never crash the watch loop.
            log.warning("ntfy notification failed: %s", exc)
