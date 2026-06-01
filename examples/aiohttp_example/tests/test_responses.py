"""
Response types — all the ways to configure what the mock server returns.

The mock supports static responses (JSON, text, pre-built objects),
dynamic responses (callables), and sequences for multistep scenarios.
"""

from aiohttp import ClientSession
from aiohttp.web import Response, json_response
from async_pytest_httpserver import HTTPServerMock

from app.clients import WeatherClient


async def test_respond_with_json(
    weather_client: WeatherClient, weather_mock: HTTPServerMock
):
    """
    respond_with_json is the most common case: return a JSON payload.
    Optional keyword args: status=, headers=.
    """
    # Arrange
    weather_mock.expect_request(
        "/weather", method="GET", query_string={"city": "Oslo"}
    ).respond_with_json({"city": "Oslo", "temp": 5, "unit": "C"})

    # Act
    result = await weather_client.get_current("Oslo")

    # Assert
    assert result["city"] == "Oslo"
    assert result["temp"] == 5


async def test_respond_with_json_custom_status(mock: HTTPServerMock):
    """
    Non-200 status codes are often needed to test error paths.
    """
    # Arrange
    mock.expect_request("/resource", method="POST").respond_with_json(
        {"id": 42}, status=201
    )

    # Act
    async with ClientSession() as session:
        resp = await session.post(mock.url_for("/resource"))

    # Assert
    assert resp.status == 201
    assert (await resp.json())["id"] == 42


async def test_respond_with_json_custom_headers(mock: HTTPServerMock):
    """
    Headers let you set pagination tokens, correlation IDs, etc.
    """
    # Arrange
    mock.expect_request("/items", method="GET").respond_with_json(
        {"items": []},
        headers={"X-Total-Count": "0", "X-Page": "1"},
    )

    # Act
    async with ClientSession() as session:
        resp = await session.get(mock.url_for("/items"))

    # Assert
    assert resp.headers["X-Total-Count"] == "0"


async def test_respond_with_data_text(mock: HTTPServerMock):
    """
    respond_with_data is for non-JSON text responses.
    Default content-type is text/plain.
    """
    # Arrange
    mock.expect_request("/ping", method="GET").respond_with_data("pong")

    # Act
    async with ClientSession() as session:
        resp = await session.get(mock.url_for("/ping"))

    # Assert
    assert await resp.text() == "pong"
    assert resp.status == 200


async def test_respond_with_data_xml(mock: HTTPServerMock):
    """
    Custom content-type lets you mock any text-based format.
    """
    # Arrange
    mock.expect_request("/feed", method="GET").respond_with_data(
        "<feed><entry>Weather</entry></feed>",
        content_type="application/xml",
    )

    # Act
    async with ClientSession() as session:
        resp = await session.get(mock.url_for("/feed"))

    # Assert
    assert "xml" in resp.content_type
    assert "<feed>" in await resp.text()


async def test_respond_with_data_empty_no_content(mock: HTTPServerMock):
    """
    204 No Content is common for DELETE and PUT operations.
    """

    # Arrange
    mock.expect_request("/resource/1", method="DELETE").respond_with_data(
        "", status=204
    )

    # Act
    async with ClientSession() as session:
        resp = await session.delete(mock.url_for("/resource/1"))

    # Assert
    assert resp.status == 204


async def test_respond_with_prebuilt_response(mock: HTTPServerMock):
    """
    respond_with_response accepts any aiohttp Response object.
    Useful when you already have a Response to reuse across tests.
    """
    # Arrange
    prebuilt = json_response({"status": "ok"}, status=200)
    mock.expect_request("/status", method="GET").respond_with_response(
        prebuilt
    )

    # Act
    async with ClientSession() as session:
        resp = await session.get(mock.url_for("/status"))

    # Assert
    assert resp.status == 200
    assert (await resp.json())["status"] == "ok"


async def test_handler_without_response_returns_500(mock: HTTPServerMock):
    """
    Forgetting to call respond_with_* is a common mistake.
    The mock returns 500 with a clear error message.
    """
    # Arrange
    mock.expect_request("/oops", method="GET")  # no respond_with_* call

    # Act
    async with ClientSession() as session:
        resp = await session.get(mock.url_for("/oops"))

    # Assert
    assert resp.status == 500


async def test_respond_with_async_handler(mock: HTTPServerMock):
    """
    respond_with_handler accepts an async coroutine.
    The handler receives the full request object and returns a Response.
    Use this when the response must depend on the request content.
    """

    # Arrange
    async def echo_handler(request):
        body = await request.json()
        return Response(
            text=f"echo: {body.get('message', '')}",
            content_type="text/plain",
        )

    mock.expect_request("/echo", method="POST").respond_with_handler(
        echo_handler
    )

    # Act
    async with ClientSession() as session:
        resp = await session.post(
            mock.url_for("/echo"), json={"message": "hi"}
        )

    # Assert
    assert await resp.text() == "echo: hi"


async def test_respond_with_sync_handler(mock: HTTPServerMock):
    """
    Sync handlers are also supported — no async required.
    """
    # Arrange
    counter = {"n": 0}

    def counting_handler(request):
        counter["n"] += 1
        return Response(text=str(counter["n"]))

    mock.expect_request("/count", method="GET").respond_with_handler(
        counting_handler
    )

    # Act
    async with ClientSession() as session:
        r1 = await session.get(mock.url_for("/count"))
        r2 = await session.get(mock.url_for("/count"))

    # Assert
    assert await r1.text() == "1"
    assert await r2.text() == "2"


async def test_sequence_retry_scenario(mock: HTTPServerMock):
    """
    respond_with_sequence lets you define a list of responses
        served in order. The last item repeats indefinitely.
    Perfect for testing retry logic: fail twice, then succeed.
    """
    # Arrange
    mock.expect_request("/api", method="POST").respond_with_sequence(
        [
            (503, {"error": "unavailable"}),
            (503, {"error": "unavailable"}),
            (201, {"id": 99}),
        ]
    )

    # Act
    responses = []
    async with ClientSession() as session:
        for _ in range(3):
            resp = await session.post(mock.url_for("/api"))
            responses.append(resp.status)

    # Assert
    assert responses == [503, 503, 201]


async def test_sequence_with_response_objects(mock: HTTPServerMock):
    """
    Items can be web.Response objects alongside tuples.
    """
    # Arrange
    mock.expect_request("/data", method="GET").respond_with_sequence(
        [
            Response(status=429, text="rate limited"),
            Response(status=200, text="ok"),
        ]
    )

    # Act
    async with ClientSession() as session:
        r1 = await session.get(mock.url_for("/data"))
        r2 = await session.get(mock.url_for("/data"))
        r3 = await session.get(mock.url_for("/data"))

    # Assert
    assert r1.status == 429
    assert r2.status == 200
    assert r3.status == 200


async def test_sequence_with_callable_item(mock: HTTPServerMock):
    """
    Callables in sequences enable dynamic responses for specific steps.
    """
    # Arrange
    step = {"n": 0}

    def dynamic(request):
        step["n"] += 1
        return json_response({"attempt": step["n"]})

    mock.expect_request("/task", method="POST").respond_with_sequence(
        [
            (500, {"error": "busy"}),
            dynamic,
        ]
    )

    # Act
    async with ClientSession() as session:
        r1 = await session.post(mock.url_for("/task"))
        r2 = await session.post(mock.url_for("/task"))
        r3 = await session.post(mock.url_for("/task"))

    # Assert
    assert r1.status == 500
    assert (await r2.json())["attempt"] == 1
    assert (await r3.json())["attempt"] == 2
