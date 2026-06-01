from __future__ import annotations

import pytest
from aiohttp.web import Request, Response

from async_pytest_httpserver import HTTPServerMock


async def test_respond_with_json(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    handler = some_http_service_mock.expect_request("/api", method="POST")
    handler.respond_with_json({"result": "ok"})

    # Act
    resp = await client.post(
        some_http_service_mock.url_for("/api"),
        json={"input": 1},
    )

    # Assert
    assert resp.ok
    assert await resp.json() == {"result": "ok"}
    handler.call_log.assert_called_once()
    handler.call_log.assert_called_with(json={"input": 1})


async def test_respond_with_data(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    handler = some_http_service_mock.expect_request("/ping", method="GET")
    handler.respond_with_data("pong", status=200)

    # Act
    resp = await client.get(some_http_service_mock.url_for("/ping"))

    # Assert
    assert resp.status == 200
    assert await resp.text() == "pong"
    handler.call_log.assert_called_once()


async def test_respond_with_async_handler(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    async def handler_fn(request: Request) -> Response:
        body = await request.json()
        return Response(text=f"echo:{body['msg']}")

    handler = some_http_service_mock.expect_request("/echo", method="POST")
    handler.respond_with_handler(handler_fn)

    # Act
    resp = await client.post(
        some_http_service_mock.url_for("/echo"), json={"msg": "hello"}
    )

    # Assert
    assert await resp.text() == "echo:hello"
    handler.call_log.assert_called_once()


async def test_respond_with_sync_handler(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    def handler_fn(request: Request) -> Response:
        return Response(text="sync_ok")

    handler = some_http_service_mock.expect_request("/sync", method="GET")
    handler.respond_with_handler(handler_fn)

    # Act
    resp = await client.get(some_http_service_mock.url_for("/sync"))

    # Assert
    assert await resp.text() == "sync_ok"


async def test_respond_with_json_custom_status(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    handler = some_http_service_mock.expect_request("/created", method="POST")
    handler.respond_with_json({"id": 1}, status=201)

    # Act
    resp = await client.post(some_http_service_mock.url_for("/created"))

    # Assert
    assert resp.status == 201
    assert await resp.json() == {"id": 1}


async def test_respond_with_json_custom_headers(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    handler = some_http_service_mock.expect_request("/hdr", method="GET")
    handler.respond_with_json({}, headers={"X-Custom": "value"})

    # Act
    resp = await client.get(some_http_service_mock.url_for("/hdr"))

    # Assert
    assert resp.headers["X-Custom"] == "value"


async def test_respond_with_data_custom_content_type(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    handler = some_http_service_mock.expect_request("/xml", method="GET")
    handler.respond_with_data(
        "<root/>", content_type="application/xml", status=200
    )

    # Act
    resp = await client.get(some_http_service_mock.url_for("/xml"))

    # Assert
    assert resp.status == 200
    assert "xml" in resp.content_type
    assert await resp.text() == "<root/>"


async def test_respond_with_data_custom_headers(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    handler = some_http_service_mock.expect_request("/hdrd", method="GET")
    handler.respond_with_data("ok", headers={"X-Info": "test"})

    # Act
    resp = await client.get(some_http_service_mock.url_for("/hdrd"))

    # Assert
    assert resp.headers["X-Info"] == "test"


async def test_respond_with_response_object(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    prebuilt = Response(text="prebuilt", status=202)
    handler = some_http_service_mock.expect_request("/pre", method="GET")
    handler.respond_with_response(prebuilt)

    # Act
    resp = await client.get(some_http_service_mock.url_for("/pre"))

    # Assert
    assert resp.status == 202
    assert await resp.text() == "prebuilt"


async def test_handler_no_response_returns_500(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    some_http_service_mock.expect_request("/unconfigured", method="GET")

    # Act
    resp = await client.get(some_http_service_mock.url_for("/unconfigured"))

    # Assert
    assert resp.status == 500


async def test_sequence_with_web_response_objects(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    handler = some_http_service_mock.expect_request("/seq", method="GET")
    handler.respond_with_sequence(
        [
            Response(status=503, text="down"),
            Response(status=200, text="up"),
        ]
    )

    # Act
    r1 = await client.get(some_http_service_mock.url_for("/seq"))
    r2 = await client.get(some_http_service_mock.url_for("/seq"))
    r3 = await client.get(
        some_http_service_mock.url_for("/seq")
    )  # last persists

    # Assert
    assert r1.status == 503
    assert r2.status == 200
    assert r3.status == 200  # last response repeats


async def test_sequence_with_tuple_shorthand(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    handler = some_http_service_mock.expect_request("/retry", method="POST")
    handler.respond_with_sequence(
        [
            (503, {"error": "unavailable"}),
            (503, {"error": "unavailable"}),
            (201, {"id": 42}),
        ]
    )

    # Act
    r1 = await client.post(some_http_service_mock.url_for("/retry"))
    r2 = await client.post(some_http_service_mock.url_for("/retry"))
    r3 = await client.post(some_http_service_mock.url_for("/retry"))
    r4 = await client.post(some_http_service_mock.url_for("/retry"))

    # Assert
    assert r1.status == 503
    assert r2.status == 503
    assert r3.status == 201
    assert r4.status == 201
    assert await r3.json() == {"id": 42}
    handler.call_log.assert_call_count(4)


async def test_sequence_with_callable(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    counter = {"n": 0}

    def dynamic(request: Request) -> Response:
        counter["n"] += 1
        return Response(
            text=f'{{"call": {counter["n"]}}}',
            content_type="application/json",
        )

    handler = some_http_service_mock.expect_request("/dyn", method="GET")
    handler.respond_with_sequence(
        [
            Response(status=503),
            dynamic,
        ]
    )

    # Act
    r1 = await client.get(some_http_service_mock.url_for("/dyn"))
    r2 = await client.get(some_http_service_mock.url_for("/dyn"))
    r3 = await client.get(some_http_service_mock.url_for("/dyn"))

    # Assert
    assert r1.status == 503
    assert (await r2.json())["call"] == 1
    assert (await r3.json())["call"] == 2


async def test_sequence_single_item_always_repeats(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    handler = some_http_service_mock.expect_request("/one", method="GET")
    handler.respond_with_sequence([(200, {"only": "this"})])

    # Act
    r1 = await client.get(some_http_service_mock.url_for("/one"))
    r2 = await client.get(some_http_service_mock.url_for("/one"))

    # Assert
    assert await r1.json() == {"only": "this"}
    assert await r2.json() == {"only": "this"}


async def test_sequence_with_async_callable(
    client, some_http_service_mock: HTTPServerMock
):
    """Async callable inside respond_with_sequence must be awaited."""
    # Arrange
    counter = {"n": 0}

    async def async_dynamic(request: Request) -> Response:
        counter["n"] += 1
        return Response(
            text=f'{{"call": {counter["n"]}}}',
            content_type="application/json",
        )

    handler = some_http_service_mock.expect_request("/adyn", method="GET")
    handler.respond_with_sequence(
        [
            Response(status=503),
            async_dynamic,
        ]
    )

    # Act
    r1 = await client.get(some_http_service_mock.url_for("/adyn"))
    r2 = await client.get(some_http_service_mock.url_for("/adyn"))
    r3 = await client.get(some_http_service_mock.url_for("/adyn"))

    # Assert
    assert r1.status == 503
    assert (await r2.json())["call"] == 1
    assert (await r3.json())["call"] == 2


def test_respond_with_sequence_empty_list_raises(
    some_http_service_mock: HTTPServerMock,
):
    """respond_with_sequence([]) must raise ValueError immediately."""
    # Arrange
    handler = some_http_service_mock.expect_request("/seq-empty", method="GET")

    # Act / Assert
    with pytest.raises(ValueError, match="must not be empty"):
        handler.respond_with_sequence([])
