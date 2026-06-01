from __future__ import annotations

import pytest

from async_pytest_httpserver import HTTPServerMock


async def test_oneshot_handler_serves_once(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    handler = some_http_service_mock.expect_oneshot_request(
        "/init", method="POST"
    )
    handler.respond_with_json({"initialized": True})

    # Act
    first = await client.post(some_http_service_mock.url_for("/init"))
    second = await client.post(some_http_service_mock.url_for("/init"))

    # Assert
    assert first.ok
    assert second.status == 404
    handler.call_log.assert_called_once()


async def test_check_raises_for_uncalled_oneshot(
    some_http_service_mock: HTTPServerMock,
):
    # Arrange
    some_http_service_mock.expect_oneshot_request("/never").respond_with_json(
        {}
    )

    # Act
    ...

    # Assert
    with pytest.raises(AssertionError, match="1 handler"):
        some_http_service_mock.check()


async def test_ordered_handlers_in_sequence(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    h1 = some_http_service_mock.expect_ordered_request("/step", method="POST")
    h1.respond_with_json({"step": 1})

    h2 = some_http_service_mock.expect_ordered_request("/step", method="POST")
    h2.respond_with_json({"step": 2})

    # Act
    r1 = await client.post(some_http_service_mock.url_for("/step"))
    r2 = await client.post(some_http_service_mock.url_for("/step"))

    # Assert
    assert await r1.json() == {"step": 1}
    assert await r2.json() == {"step": 2}
    h1.call_log.assert_called_once()
    h2.call_log.assert_called_once()
    some_http_service_mock.check()


async def test_ordered_handler_wrong_order_returns_500(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    some_http_service_mock.expect_ordered_request(
        "/first", method="GET"
    ).respond_with_json({})

    # Act
    resp = await client.get(some_http_service_mock.url_for("/wrong"))

    # Assert
    assert resp.status == 500


async def test_check_raises_for_uncalled_ordered(
    some_http_service_mock: HTTPServerMock,
):
    # Arrange
    some_http_service_mock.expect_ordered_request("/a").respond_with_json({})
    some_http_service_mock.expect_ordered_request("/b").respond_with_json({})

    # Act
    ...

    # Assert
    with pytest.raises(AssertionError, match="2 handler"):
        some_http_service_mock.check()


async def test_unregistered_route_returns_404(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    ...

    # Act
    resp = await client.get(some_http_service_mock.url_for("/no-such-route"))

    # Assert
    assert resp.status == 404


async def test_bake_oneshot_request(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    baked = some_http_service_mock.bake(method="DELETE")
    handler = baked.expect_oneshot_request("/res")
    handler.respond_with_json({"deleted": True})

    # Act
    first = await client.delete(some_http_service_mock.url_for("/res"))
    second = await client.delete(some_http_service_mock.url_for("/res"))

    # Assert
    assert first.ok
    assert second.status == 404


async def test_bake_ordered_request(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    baked = some_http_service_mock.bake(method="POST")
    h1 = baked.expect_ordered_request("/step")
    h1.respond_with_json({"n": 1})
    h2 = baked.expect_ordered_request("/step")
    h2.respond_with_json({"n": 2})

    # Act
    r1 = await client.post(some_http_service_mock.url_for("/step"))
    r2 = await client.post(some_http_service_mock.url_for("/step"))

    # Assert
    assert await r1.json() == {"n": 1}
    assert await r2.json() == {"n": 2}
