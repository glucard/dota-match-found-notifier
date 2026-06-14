from __future__ import annotations

import pytest

from d2kit.stats.stratz.client import StratzClient, StratzError


def test_query_returns_data(httpx_mock):
    httpx_mock.add_response(json={"data": {"player": {"id": 7}}})
    with StratzClient("token") as client:
        assert client.query("{ player { id } }") == {"player": {"id": 7}}


def test_query_raises_on_graphql_errors(httpx_mock):
    httpx_mock.add_response(json={"errors": [{"message": "nope"}]})
    with StratzClient("token") as client, pytest.raises(StratzError):
        client.query("{ bad }")


def test_query_raises_on_http_error(httpx_mock):
    httpx_mock.add_response(status_code=500, text="boom")
    with StratzClient("token") as client, pytest.raises(StratzError):
        client.query("{ x }")


def test_sends_auth_header(httpx_mock):
    httpx_mock.add_response(json={"data": {}})
    with StratzClient("secrettoken") as client:
        client.query("{ x }")
    request = httpx_mock.get_requests()[0]
    assert request.headers["Authorization"] == "Bearer secrettoken"
