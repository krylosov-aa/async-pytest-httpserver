import pytest
from aiohttp import ClientSession
from async_pytest_httpserver import (
    HTTPServerMock,
    M,
    RequestMatcher,
    StartsWith,
)

from app.clients import WeatherClient


async def test_assert_called_once(
    weather_client: WeatherClient, weather_mock: HTTPServerMock
):
    # Arrange
    handler = weather_mock.expect_request(
        "/weather", method="GET", query_string={"city": "Rome"}
    )
    handler.respond_with_json({"city": "Rome", "temp": 28})

    # Act
    await weather_client.get_current("Rome")

    # Assert
    handler.call_log.assert_called_once()


async def test_assert_called(mock: HTTPServerMock):
    # Arrange
    handler = mock.expect_request("/ping", method="GET")
    handler.respond_with_json({})

    # Act
    async with ClientSession() as session:
        await session.get(mock.url_for("/ping"))
        await session.get(mock.url_for("/ping"))

    # Assert
    handler.call_log.assert_called()  # Passes even though called twice


async def test_assert_not_called(mock: HTTPServerMock):
    # Arrange
    alert_handler = mock.expect_request("/alerts", method="POST")
    alert_handler.respond_with_data("", status=204)

    # Act
    ...

    # Assert
    alert_handler.call_log.assert_not_called()


async def test_assert_call_count(mock: HTTPServerMock):
    # Arrange
    handler = mock.expect_request("/tick", method="POST")
    handler.respond_with_json({})

    # Act
    async with ClientSession() as session:
        for _ in range(3):
            await session.post(mock.url_for("/tick"))

    # Assert
    handler.call_log.assert_call_count(3)


async def test_assert_called_with_json(
    weather_client: WeatherClient, weather_mock: HTTPServerMock
):
    # Arrange
    handler = weather_mock.expect_request("/alerts", method="POST")
    handler.respond_with_data("", status=204)

    # Act
    await weather_client.report_alert("Madrid", "Heatwave warning")

    # Assert
    handler.call_log.assert_called_with(
        json={"city": "Madrid", "message": "Heatwave warning"}
    )


async def test_assert_called_with_query(mock: HTTPServerMock):
    # Arrange
    handler = mock.expect_request("/search", method="GET")
    handler.respond_with_json({"results": []})

    # Act
    async with ClientSession() as session:
        await session.get(mock.url_for("/search?q=python&page=2"))

    # Assert
    handler.call_log.assert_called_with(query={"q": "python", "page": "2"})


async def test_assert_called_with_headers(mock: HTTPServerMock):
    # Arrange
    handler = mock.expect_request("/resource", method="GET")
    handler.respond_with_json({})

    # Act
    async with ClientSession() as session:
        await session.get(
            mock.url_for("/resource"),
            headers={"X-Trace-Id": "abc-123"},
        )

    # Assert
    handler.call_log.assert_called_with(headers={"X-Trace-Id": "abc-123"})


async def test_assert_called_with_call_index(mock: HTTPServerMock):
    # Arrange
    handler = mock.expect_request("/items", method="POST")
    handler.respond_with_json({})

    # Act
    async with ClientSession() as session:
        await session.post(mock.url_for("/items"), json={"name": "apple"})
        await session.post(mock.url_for("/items"), json={"name": "banana"})
        await session.post(mock.url_for("/items"), json={"name": "cherry"})

    # Assert
    handler.call_log.assert_called_with(call_index=0, json={"name": "apple"})
    handler.call_log.assert_called_with(call_index=1, json={"name": "banana"})
    handler.call_log.assert_called_with(json={"name": "cherry"})  # last


async def test_call_log_last(mock: HTTPServerMock):
    # Arrange
    handler = mock.expect_request("/orders", method="POST")
    handler.respond_with_json({"id": 1})

    # Act
    async with ClientSession() as session:
        await session.post(mock.url_for("/orders"), json={"item": "book"})
        await session.post(mock.url_for("/orders"), json={"item": "pen"})

    # Assert
    last = handler.call_log.last
    assert last.json == {"item": "pen"}
    assert last.method == "POST"
    assert last.path == "/orders"


async def test_iterate_call_log(mock: HTTPServerMock):
    # Arrange
    handler = mock.expect_request("/log", method="POST")
    handler.respond_with_json({})

    items = ["alpha", "beta", "gamma"]

    # Act
    async with ClientSession() as session:
        for item in items:
            await session.post(mock.url_for("/log"), json={"item": item})

    # Assert
    assert len(handler.call_log) == 3
    for idx, call in enumerate(handler.call_log):
        assert call.json == {"item": items[idx]}


async def test_server_log(mock: HTTPServerMock):
    # Arrange
    mock.expect_request("/users", method="GET").respond_with_json([])
    mock.expect_request("/orders", method="GET").respond_with_json([])

    # Act
    async with ClientSession() as session:
        await session.get(mock.url_for("/users"))
        await session.get(mock.url_for("/orders"))
        await session.get(mock.url_for("/users"))

    # Assert
    assert len(mock.log) == 3
    paths = [call.path for call, _ in mock.log]
    assert paths == ["/users", "/orders", "/users"]


async def test_assert_request_made(mock: HTTPServerMock):
    # Arrange
    mock.expect_request(
        path=StartsWith("/api/"), method="GET"
    ).respond_with_json({})
    mock.expect_request("/health", method="GET").respond_with_json(
        {"ok": True}
    )

    # Act
    async with ClientSession() as session:
        await session.get(mock.url_for("/api/users"))
        await session.get(mock.url_for("/api/products"))
        await session.get(mock.url_for("/health"))

    # Assert
    mock.assert_request_made(
        M(path=StartsWith("/api/"), method="GET"), count=2
    )
    mock.assert_request_made(
        RequestMatcher(path="/health", method="GET"), count=1
    )


async def test_iter_matching_requests(mock: HTTPServerMock):
    # Arrange
    mock.expect_request("/events", method="POST").respond_with_json({})

    # Act
    async with ClientSession() as session:
        await session.post(mock.url_for("/events"), json={"type": "click"})
        await session.post(mock.url_for("/events"), json={"type": "scroll"})
        await session.post(mock.url_for("/events"), json={"type": "click"})

    # Assert
    click_matcher = RequestMatcher(
        "/events", method="POST", json_contains={"type": "click"}
    )
    clicks = list(mock.iter_matching_requests(click_matcher))
    assert len(clicks) == 2
    assert all(
        isinstance(call.json, dict) and call.json["type"] == "click"
        for call, _ in clicks
    )


async def test_check_oneshot_and_ordered(mock: HTTPServerMock):
    # Arrange
    # NOTE: ordered handlers block oneshot while the queue is non-empty —
    # register all ordered steps first, then add oneshot handlers.
    h1 = mock.expect_ordered_request("/stage/1", method="POST")
    h1.respond_with_json({"stage": 1})

    h2 = mock.expect_ordered_request("/stage/2", method="POST")
    h2.respond_with_json({"stage": 2})

    h3 = mock.expect_oneshot_request("/finish", method="POST")
    h3.respond_with_json({"complete": True})

    # Act
    async with ClientSession() as session:
        await session.post(mock.url_for("/stage/1"))
        await session.post(mock.url_for("/stage/2"))
        await session.post(mock.url_for("/finish"))

    # Assert
    mock.check()


async def test_check_fails_for_uncalled_handlers(mock: HTTPServerMock):
    # Arrange
    mock.expect_oneshot_request("/webhook", method="POST").respond_with_json(
        {}
    )

    # Act
    ...

    # Assert
    with pytest.raises(AssertionError, match="handler"):
        mock.check()


async def test_check_all_called(mock: HTTPServerMock):
    # Arrange
    h_users = mock.expect_request("/users", method="GET")
    h_users.respond_with_json([])

    h_health = mock.expect_request("/health", method="GET")
    h_health.respond_with_json({"ok": True})

    # Act
    async with ClientSession() as session:
        await session.get(mock.url_for("/users"))
        await session.get(mock.url_for("/health"))

    # Assert
    mock.check(all_called=True)


async def test_check_handler_errors(mock: HTTPServerMock):
    # Arrange
    def buggy(request):
        raise ValueError("unexpected payload")

    mock.expect_request("/process", method="POST").respond_with_handler(buggy)

    # Act
    async with ClientSession() as session:
        resp = await session.post(mock.url_for("/process"), json={"data": 1})

    # Assert
    assert resp.status == 500
    with pytest.raises(ValueError, match="unexpected payload"):
        mock.check()


async def test_format_matchers_for_debugging(mock: HTTPServerMock):
    # Arrange
    mock.expect_request("/a", method="GET").respond_with_json({})
    mock.expect_oneshot_request("/b", method="POST").respond_with_json({})

    async with ClientSession() as session:
        await session.get(mock.url_for("/a"))

    # Act
    output = mock.format_matchers()

    # Assert
    assert "PERMANENT" in output
    assert "ONESHOT" in output
    assert "/a" in output
    assert "/b" in output

    # output:
    # Registered handlers:
    #   [PERMANENT] RequestMatcher(path='/a', method='GET') — 1 call(s)
    #   [ONESHOT]   RequestMatcher(path='/b', method='POST') — 0 call(s)
