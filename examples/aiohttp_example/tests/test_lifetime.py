"""
Handler lifetime — controls how long a registered handler stays active
and how many responses it provides.

Three lifetime modes:
- Permanent (expect_request)         — responds indefinitely
- Oneshot   (expect_oneshot_request) — responds exactly once
- Ordered   (expect_ordered_request) — strict sequential order

Plus: respond_with_sequence for multistep responses on one handler,
and bake() for pre-filled defaults across multiple registrations.
"""

import pytest
from aiohttp import ClientSession
from async_pytest_httpserver import HTTPServerMock

from app.clients import WeatherClient


async def test_permanent_responds_every_time(
    weather_client: WeatherClient, weather_mock: HTTPServerMock
):
    """
    The default: handler stays active for the whole test.
    Every matching request gets the same response.
    """
    # Arrange
    handler = weather_mock.expect_request("/weather", method="GET")
    handler.respond_with_json({"city": "London", "temp": 15})

    # Act
    r1 = await weather_client.get_current("London")
    r2 = await weather_client.get_current("London")
    r3 = await weather_client.get_current("London")

    # Assert
    assert r1["city"] == "London"
    assert r2["city"] == "London"
    assert r3["city"] == "London"
    handler.call_log.assert_call_count(3)


async def test_oneshot_responds_exactly_once(mock: HTTPServerMock):
    """
    expect_oneshot_request registers a handler that auto-removes itself
        after the first matching request.
    The second call gets 404 because the handler is gone.
    """
    # Arrange
    handler = mock.expect_oneshot_request("/setup", method="POST")
    handler.respond_with_json({"configured": True})

    # Act
    async with ClientSession() as session:
        first = await session.post(mock.url_for("/setup"))
        second = await session.post(mock.url_for("/setup"))

    # Assert
    assert first.ok
    assert second.status == 404
    handler.call_log.assert_called_once()


async def test_oneshot_check_detects_uncalled(mock: HTTPServerMock):
    """
    mock.check() fails if a oneshot handler was never called.
    Use it at the end of a test to catch missed interactions.
    """
    # Arrange
    mock.expect_oneshot_request("/confirm", method="POST").respond_with_json(
        {"ok": True}
    )

    # Act
    ...

    # Assert
    with pytest.raises(AssertionError, match="handler"):
        mock.check()


async def test_ordered_enforces_registration_sequence(mock: HTTPServerMock):
    """
    Ordered handlers must be called in exactly the order they were
        registered. Use this to test state-machine flows or wizard steps.
    """
    # Arrange
    h1 = mock.expect_ordered_request("/step/1", method="POST")
    h1.respond_with_json({"step": 1, "done": False})

    h2 = mock.expect_ordered_request("/step/2", method="POST")
    h2.respond_with_json({"step": 2, "done": False})

    h3 = mock.expect_ordered_request("/step/3", method="POST")
    h3.respond_with_json({"step": 3, "done": True})

    # Act
    async with ClientSession() as session:
        r1 = await session.post(mock.url_for("/step/1"))
        r2 = await session.post(mock.url_for("/step/2"))
        r3 = await session.post(mock.url_for("/step/3"))

    # Assert
    assert (await r1.json())["step"] == 1
    assert (await r2.json())["step"] == 2
    assert (await r3.json())["step"] == 3
    mock.check()


async def test_ordered_returns_500_on_wrong_order(mock: HTTPServerMock):
    """
    If a request doesn't match the next expected ordered handler,
        the server immediately returns 500.
    """
    # Arrange
    mock.expect_ordered_request("/step/1", method="POST").respond_with_json({})
    mock.expect_ordered_request("/step/2", method="POST").respond_with_json({})

    # Act
    async with ClientSession() as session:
        wrong_order = await session.post(mock.url_for("/step/2"))

    # Assert
    assert wrong_order.status == 500


async def test_sequence_models_retry_logic(mock: HTTPServerMock):
    """
    respond_with_sequence defines different responses for successive calls.
    The last item in the list repeats indefinitely.
    """
    # Arrange
    handler = mock.expect_request("/api/data", method="GET")
    handler.respond_with_sequence(
        [
            (503, {"error": "service unavailable"}),
            (503, {"error": "service unavailable"}),
            (200, {"data": "ready"}),
        ]
    )

    # Act
    async with ClientSession() as session:
        responses = [
            await session.get(mock.url_for("/api/data")) for _ in range(4)
        ]

    # Assert
    assert responses[0].status == 503
    assert responses[1].status == 503
    assert responses[2].status == 200
    assert responses[3].status == 200


async def test_bake_applies_method_to_all_handlers(mock: HTTPServerMock):
    """
    bake(**defaults) returns a BakedMock where every handler inherits
        the given defaults. Reduces repetition when many handlers share
        the same method, headers, or other parameters.
    """
    # Arrange
    api = mock.bake(method="POST")
    api.expect_request("/orders").respond_with_json({"id": 1})
    api.expect_request("/payments").respond_with_json({"charged": True})
    api.expect_request("/notifications").respond_with_json({"sent": True})

    # Act
    async with ClientSession() as session:
        r_orders = await session.post(mock.url_for("/orders"))
        r_payments = await session.post(mock.url_for("/payments"))
        r_notif = await session.post(mock.url_for("/notifications"))
        miss = await session.get(mock.url_for("/orders"))

    # Assert
    assert r_orders.ok
    assert r_payments.ok
    assert r_notif.ok
    assert miss.status == 404


async def test_bake_with_shared_header_requirement(mock: HTTPServerMock):
    """
    Bake headers to require an auth token on every handler.
    Individual handlers can still override defaults with **overrides.
    """
    # Arrange
    secured = mock.bake(
        method="GET",
        headers={"X-Api-Key": "my-key"},
    )
    secured.expect_request("/users").respond_with_json([])
    secured.expect_request("/products").respond_with_json([])

    # A specific handler overrides the header check
    secured.expect_request(
        "/public",
        headers=None,  # override: no header required
    ).respond_with_json({"public": True})

    # Act
    async with ClientSession() as session:
        # Authenticated requests succeed
        r_users = await session.get(
            mock.url_for("/users"), headers={"X-Api-Key": "my-key"}
        )
        # Unauthenticated request to secured endpoint fails
        r_unauth = await session.get(mock.url_for("/users"))
        # Public endpoint needs no header
        r_public = await session.get(mock.url_for("/public"))

    # Assert
    assert r_users.ok
    assert r_unauth.status == 404
    assert r_public.ok
