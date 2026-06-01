from __future__ import annotations

import time

import pytest
from aiohttp.web import Request, Response

from async_pytest_httpserver import Chain, Delay, Garbage, HTTPServerMock


async def test_delay_hook(client, some_http_service_mock: HTTPServerMock):
    # Arrange
    handler = some_http_service_mock.expect_request("/slow", method="GET")
    handler.with_post_hook(Delay(sec=0.05)).respond_with_json({"done": True})

    # Act
    start = time.monotonic()
    resp = await client.get(some_http_service_mock.url_for("/slow"))
    elapsed = time.monotonic() - start

    # Assert
    assert resp.ok
    assert elapsed >= 0.05


async def test_garbage_hook_corrupts_body(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    handler = some_http_service_mock.expect_request("/data", method="GET")
    handler.with_post_hook(Garbage(prefix_size=3, suffix_size=2))
    handler.respond_with_data("hello")

    # Act
    resp = await client.get(some_http_service_mock.url_for("/data"))
    body = await resp.read()

    # Assert
    assert len(body) == len(b"hello") + 3 + 2


async def test_chain_hook_applies_in_order(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    handler = some_http_service_mock.expect_request("/chained", method="GET")
    handler.with_post_hook(Chain(Delay(ms=10), Garbage(suffix_size=1)))
    handler.respond_with_data("ok")

    # Act
    start = time.monotonic()
    resp = await client.get(some_http_service_mock.url_for("/chained"))
    elapsed = time.monotonic() - start
    body = await resp.read()

    # Assert
    assert elapsed >= 0.01
    assert len(body) == len(b"ok") + 1


async def test_sync_post_hook_via_with_post_hook(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    def sync_hook(request: Request, response: Response) -> Response:
        return Response(text="sync_modified", status=200)

    handler = some_http_service_mock.expect_request("/sync-hook", method="GET")
    handler.with_post_hook(sync_hook).respond_with_data("original")

    # Act
    resp = await client.get(some_http_service_mock.url_for("/sync-hook"))

    # Assert
    assert await resp.text() == "sync_modified"


async def test_sync_hook_inside_chain(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    def sync_hook(request: Request, response: Response) -> Response:
        return Response(text="chain_sync", status=200)

    handler = some_http_service_mock.expect_request(
        "/chain-sync", method="GET"
    )
    handler.with_post_hook(Chain(sync_hook)).respond_with_data("original")

    # Act
    resp = await client.get(some_http_service_mock.url_for("/chain-sync"))

    # Assert
    assert await resp.text() == "chain_sync"


async def test_sequence_with_post_hooks(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    handler = some_http_service_mock.expect_request("/slow-seq", method="GET")
    handler.respond_with_sequence([(200, {"done": True})])
    handler.with_post_hook(Delay(ms=20))

    # Act
    start = time.monotonic()
    resp = await client.get(some_http_service_mock.url_for("/slow-seq"))
    elapsed = time.monotonic() - start

    # Assert
    assert resp.ok
    assert elapsed >= 0.02


async def test_garbage_hook_preserves_custom_headers(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    handler = some_http_service_mock.expect_request("/garb", method="GET")
    handler.with_post_hook(Garbage(suffix_size=2))
    handler.respond_with_json({"ok": True}, headers={"X-Custom": "preserved"})

    # Act
    resp = await client.get(some_http_service_mock.url_for("/garb"))

    # Assert
    assert resp.headers.get("X-Custom") == "preserved"


def test_delay_no_args_raises():
    with pytest.raises(TypeError, match="Specify"):
        Delay()  # type: ignore[call-overload]


def test_delay_both_args_raises():
    with pytest.raises(TypeError, match="both"):
        Delay(sec=1.0, ms=100)  # type: ignore[call-overload]
