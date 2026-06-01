"""
Post-hooks — transform the response after it is built but before it is sent.

Hooks are attached with handler.with_post_hook(hook) and applied in order.
Built-in hooks: Delay (latency), Garbage (corruption).
Chain composes multiple hooks sequentially.
Custom hooks are plain callables: (request, response) -> response.
"""

import time

from aiohttp import ClientSession
from async_pytest_httpserver import Chain, Delay, Garbage, HTTPServerMock


async def test_delay_simulates_slow_server(mock: HTTPServerMock):
    """
    Delay pauses delivery of the response.
    Use it to test client timeout handling or loading states.
    """
    # Arrange
    handler = mock.expect_request("/slow", method="GET")
    handler.with_post_hook(Delay(ms=80)).respond_with_json({"ready": True})

    # Act
    start = time.monotonic()
    async with ClientSession() as session:
        resp = await session.get(mock.url_for("/slow"))
    elapsed = time.monotonic() - start

    # Assert
    assert resp.ok
    assert elapsed >= 0.08


async def test_garbage_adds_random_bytes(mock: HTTPServerMock):
    """
    Garbage(prefix_size, suffix_size) prepends and/or appends random bytes
        to the response body. Use it to test your error-handling code when
        the server returns malformed or partial data.
    """
    # Arrange
    handler = mock.expect_request("/data", method="GET")
    handler.with_post_hook(Garbage(prefix_size=4, suffix_size=3))
    handler.respond_with_data("hello")

    # Act
    async with ClientSession() as session:
        resp = await session.get(mock.url_for("/data"))
    body = await resp.read()

    # Assert
    # The body is longer than the original "hello"
    assert len(body) == len(b"hello") + 4 + 3
    # The original content is somewhere in the middle
    assert b"hello" in body


async def test_chain_applies_hooks_in_order(mock: HTTPServerMock):
    """
    Chain(*hooks) applies each hook to the response in sequence.
    The output of each hook becomes the input of the next.
    """
    # Arrange
    handler = mock.expect_request("/unreliable", method="GET")
    handler.with_post_hook(Chain(Delay(ms=30), Garbage(suffix_size=2)))
    handler.respond_with_data("data")

    # Act
    start = time.monotonic()
    async with ClientSession() as session:
        resp = await session.get(mock.url_for("/unreliable"))
    elapsed = time.monotonic() - start
    body = await resp.read()

    # Assert
    assert elapsed >= 0.03  # Delay was applied
    assert len(body) == len(b"data") + 2  # Garbage appended


async def test_custom_async_hook_modifies_response(mock: HTTPServerMock):
    """
    Any async callable (request, response) -> response can be used as a hook.
    Useful for injecting tracing headers, modifying status codes,
        or wrapping the body.
    """

    # Arrange
    async def inject_trace_header(request, response):
        trace_id = request.headers.get("X-Request-Id", "none")
        response.headers["X-Trace-Id"] = trace_id
        return response

    handler = mock.expect_request("/traced", method="GET")
    handler.with_post_hook(inject_trace_header)
    handler.respond_with_json({"ok": True})

    # Act
    async with ClientSession() as session:
        resp = await session.get(
            mock.url_for("/traced"),
            headers={"X-Request-Id": "req-42"},
        )

    # Assert
    assert resp.headers["X-Trace-Id"] == "req-42"


async def test_custom_sync_hook_modifies_response(mock: HTTPServerMock):
    """
    Sync hooks work exactly like async hooks — just without await.
    """

    # Arrange
    def inject_trace_header(request, response):
        trace_id = request.headers.get("X-Request-Id", "none")
        response.headers["X-Trace-Id"] = trace_id
        return response

    handler = mock.expect_request("/traced", method="GET")
    handler.with_post_hook(inject_trace_header)
    handler.respond_with_json({"ok": True})

    # Act
    async with ClientSession() as session:
        resp = await session.get(
            mock.url_for("/traced"),
            headers={"X-Request-Id": "req-42"},
        )

    # Assert
    assert resp.headers["X-Trace-Id"] == "req-42"


async def test_hook_applies_to_every_sequence_item(mock: HTTPServerMock):
    """
    Hooks are applied after every item in a sequence, including each
        retry response. This lets you combine latency simulation with
        multistep scenarios.
    """
    # Arrange
    handler = mock.expect_request("/task", method="POST")
    handler.respond_with_sequence(
        [
            (503, {"error": "busy"}),
            (200, {"result": "done"}),
        ]
    )
    delay_sec = 0.02
    handler.with_post_hook(Delay(sec=delay_sec))

    # Act
    start = time.monotonic()
    async with ClientSession() as session:
        r1 = await session.post(mock.url_for("/task"))
        r2 = await session.post(mock.url_for("/task"))
    elapsed = time.monotonic() - start

    # Assert
    assert r1.status == 503
    assert r2.status == 200
    assert elapsed >= (2 * delay_sec)


async def test_custom_no_handler_status_code(http_server):
    """
    By default, unmatched requests return 404.
    Pass no_handler_status_code= to change this.
    """
    # Arrange
    mock = await http_server(no_handler_status_code=503)
    mock.expect_request("/known", method="GET").respond_with_json({})

    # Act
    async with ClientSession() as session:
        known = await session.get(mock.url_for("/known"))
        unknown = await session.get(mock.url_for("/unknown"))

    # Assert
    assert known.ok
    assert unknown.status == 503
