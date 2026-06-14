from __future__ import annotations

import httpx
import pytest

from d2kit.notify.ntfy import NtfyNotifier


def test_empty_topic_rejected():
    with pytest.raises(ValueError, match="topic"):
        NtfyNotifier("https://ntfy.sh", "")


def test_send_posts_expected_request(monkeypatch):
    captured = {}

    def fake_post(self, url, *, content, headers):
        captured["url"] = url
        captured["content"] = content
        captured["headers"] = headers
        return httpx.Response(200, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    NtfyNotifier("https://ntfy.sh/", "my-topic").send(
        title="Match Found!",
        message="accept now",
        priority=5,
        tags=["video_game", "rotating_light"],
        click="https://example.com",
    )

    assert captured["url"] == "https://ntfy.sh/my-topic"
    assert captured["content"] == b"accept now"
    assert captured["headers"]["Title"] == "Match Found!"
    assert captured["headers"]["Priority"] == "5"
    assert captured["headers"]["Tags"] == "video_game,rotating_light"
    assert captured["headers"]["Click"] == "https://example.com"


def test_non_ascii_title_is_sanitized_not_crashing(monkeypatch):
    captured = {}

    def fake_post(self, url, *, content, headers):
        captured["headers"] = headers
        return httpx.Response(200, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    # An emoji in the title must not raise (HTTP headers are ASCII-only).
    NtfyNotifier("https://ntfy.sh", "t").send(title="d2kit test ✅", message="hi ✅")

    title = captured["headers"]["Title"]
    title.encode("ascii")  # would raise if any non-ASCII slipped through
    assert "✅" not in title


def test_send_swallows_http_errors(monkeypatch):
    def boom(*a, **k):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(httpx.Client, "post", boom)
    # Must not raise — a failed notification cannot crash the watch loop.
    NtfyNotifier("https://ntfy.sh", "t").send(title="x", message="y")
