from __future__ import annotations

import pytest
from aiohttp.web import Request, Response

from async_pytest_httpserver import (
    HTTPServerMock,
    M,
    RequestMatcher,
    StartsWith,
)


async def test_clear_allows_re_registration(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    h1 = some_http_service_mock.expect_request("/api", method="GET")
    h1.respond_with_json({"v": 1})
    r1 = await client.get(some_http_service_mock.url_for("/api"))
    assert await r1.json() == {"v": 1}

    # Act
    some_http_service_mock.clear()
    h2 = some_http_service_mock.expect_request("/api", method="GET")
    h2.respond_with_json({"v": 2})

    # Assert
    r2 = await client.get(some_http_service_mock.url_for("/api"))
    assert await r2.json() == {"v": 2}


async def test_url_for(some_http_service_mock: HTTPServerMock):
    # Arrange
    ...

    # Act
    url = some_http_service_mock.url_for("/api/v1/users")

    # Assert
    assert url.startswith("http://")
    assert url.endswith("/api/v1/users")


async def test_server_log_records_calls(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    some_http_service_mock.expect_request(
        "/a", method="GET"
    ).respond_with_json({})
    some_http_service_mock.expect_request(
        "/b", method="POST"
    ).respond_with_json({})

    # Act
    await client.get(some_http_service_mock.url_for("/a"))
    await client.post(some_http_service_mock.url_for("/b"), json={})

    # Assert
    assert len(some_http_service_mock.log) == 2
    call_a, _ = some_http_service_mock.log[0]
    assert call_a.path == "/a"
    call_b, _ = some_http_service_mock.log[1]
    assert call_b.path == "/b"


async def test_assert_request_made(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    some_http_service_mock.expect_request(
        "/x", method="GET"
    ).respond_with_json({})
    matcher = RequestMatcher("/x", method="GET")

    # Act
    await client.get(some_http_service_mock.url_for("/x"))
    await client.get(some_http_service_mock.url_for("/x"))

    # Assert
    some_http_service_mock.assert_request_made(matcher, count=2)


async def test_assert_request_made_fails_on_wrong_count(
    some_http_service_mock: HTTPServerMock,
):
    # Arrange
    matcher = RequestMatcher("/missing", method="GET")

    # Act
    ...

    # Assert
    with pytest.raises(AssertionError, match="Expected 1 request"):
        some_http_service_mock.assert_request_made(matcher, count=1)


async def test_iter_matching_requests(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    some_http_service_mock.expect_request(
        "/items", method="GET"
    ).respond_with_json({})
    some_http_service_mock.expect_request(
        "/other", method="GET"
    ).respond_with_json({})
    matcher = RequestMatcher("/items", method="GET")

    # Act
    await client.get(some_http_service_mock.url_for("/items"))
    await client.get(some_http_service_mock.url_for("/other"))
    await client.get(some_http_service_mock.url_for("/items"))

    # Assert
    matches = list(some_http_service_mock.iter_matching_requests(matcher))
    assert len(matches) == 2
    assert all(call.path == "/items" for call, _ in matches)


async def test_check_handler_errors_catches_exception(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    def broken_handler(request: Request) -> Response:
        raise RuntimeError("handler exploded")

    some_http_service_mock.expect_request(
        "/boom", method="GET"
    ).respond_with_handler(broken_handler)

    # Act
    resp = await client.get(some_http_service_mock.url_for("/boom"))

    # Assert
    assert resp.status == 500
    with pytest.raises(RuntimeError, match="handler exploded"):
        some_http_service_mock.check_handler_errors()


async def test_check_includes_handler_errors(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    def broken_handler(request: Request) -> Response:
        raise ValueError("oops")

    some_http_service_mock.expect_request(
        "/err", method="GET"
    ).respond_with_handler(broken_handler)

    # Act
    await client.get(some_http_service_mock.url_for("/err"))

    # Assert
    with pytest.raises(ValueError, match="oops"):
        some_http_service_mock.check()


async def test_format_matchers(some_http_service_mock: HTTPServerMock):
    # Arrange
    some_http_service_mock.expect_request(
        "/p", method="GET"
    ).respond_with_json({})
    some_http_service_mock.expect_oneshot_request(
        "/o", method="POST"
    ).respond_with_json({})

    # Act
    output = some_http_service_mock.format_matchers()

    # Assert
    assert "PERMANENT" in output
    assert "ONESHOT" in output
    assert "/p" in output
    assert "/o" in output


async def test_no_handler_status_code(http_server, client):
    # Arrange
    mock = await http_server(no_handler_status_code=501)

    # Act
    resp = await client.get(mock.url_for("/nowhere"))

    # Assert
    assert resp.status == 501


async def test_bake_applies_method_default(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    baked = some_http_service_mock.bake(method="POST")
    baked.expect_request("/create").respond_with_json({"created": True})

    # Act
    resp = await client.post(some_http_service_mock.url_for("/create"))

    # Assert
    assert resp.ok
    assert await resp.json() == {"created": True}


async def test_bake_override_per_call(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    baked = some_http_service_mock.bake(method="POST")
    baked.expect_request("/read", method="GET").respond_with_json({"ok": True})

    # Act
    resp = await client.get(some_http_service_mock.url_for("/read"))

    # Assert
    assert resp.ok


async def test_bake_applies_header_default(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    baked = some_http_service_mock.bake(
        method="GET", headers={"X-Api-Key": "secret"}
    )
    handler = baked.expect_request("/secure")
    handler.respond_with_json({"ok": True})

    # Act
    resp_ok = await client.get(
        some_http_service_mock.url_for("/secure"),
        headers={"X-Api-Key": "secret"},
    )
    resp_fail = await client.get(some_http_service_mock.url_for("/secure"))

    # Assert
    assert resp_ok.ok
    assert resp_fail.status == 404


async def test_assert_request_made_json_matcher(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    some_http_service_mock.expect_request(
        "/jm", method="POST"
    ).respond_with_json({})
    matcher = RequestMatcher("/jm", method="POST", json={"key": "yes"})

    # Act
    await client.post(
        some_http_service_mock.url_for("/jm"), json={"key": "yes"}
    )
    await client.post(
        some_http_service_mock.url_for("/jm"), json={"key": "no"}
    )

    # Assert
    some_http_service_mock.assert_request_made(matcher, count=1)


async def test_assert_request_made_query_matcher(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    some_http_service_mock.expect_request(
        "/qm", method="GET"
    ).respond_with_json({})
    matcher = RequestMatcher("/qm", method="GET", query_string={"p": "1"})

    # Act
    await client.get(some_http_service_mock.url_for("/qm?p=1"))
    await client.get(some_http_service_mock.url_for("/qm?p=2"))

    # Assert
    some_http_service_mock.assert_request_made(matcher, count=1)


async def test_assert_request_made_count_zero(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    some_http_service_mock.expect_request(
        "/nope", method="GET"
    ).respond_with_json({})
    matcher = RequestMatcher("/other", method="GET")

    # Act
    await client.get(some_http_service_mock.url_for("/nope"))

    # Assert
    some_http_service_mock.assert_request_made(matcher, count=0)


async def test_iter_matching_requests_empty(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    some_http_service_mock.expect_request(
        "/e", method="GET"
    ).respond_with_json({})
    matcher = RequestMatcher("/other", method="GET")

    # Act
    await client.get(some_http_service_mock.url_for("/e"))

    # Assert
    results = list(some_http_service_mock.iter_matching_requests(matcher))
    assert results == []


def test_no_handler_status_code_constructor():
    # Act
    mock = HTTPServerMock(no_handler_status_code=418)

    # Assert
    assert mock.no_handler_status_code == 418


async def test_clear_resets_handler_errors(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    def broken(request: Request) -> Response:
        raise RuntimeError("boom")

    some_http_service_mock.expect_request(
        "/br", method="GET"
    ).respond_with_handler(broken)
    await client.get(some_http_service_mock.url_for("/br"))

    # Act
    some_http_service_mock.clear()

    # Assert
    some_http_service_mock.check()


async def test_format_matchers_empty(some_http_service_mock: HTTPServerMock):
    # Arrange

    # Act
    output = some_http_service_mock.format_matchers()

    # Assert
    assert "Registered handlers:" in output
    assert "PERMANENT" not in output and "0 call" not in output


async def test_two_independent_mock_servers(http_server, client):
    # Arrange
    svc_a = await http_server()
    svc_b = await http_server()
    svc_a.expect_request("/api", method="GET").respond_with_json({"from": "a"})
    svc_b.expect_request("/api", method="GET").respond_with_json({"from": "b"})

    # Act
    resp_a = await client.get(svc_a.url_for("/api"))
    resp_b = await client.get(svc_b.url_for("/api"))

    # Assert
    assert await resp_a.json() == {"from": "a"}
    assert await resp_b.json() == {"from": "b"}


async def test_assert_request_made_wrong_method(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    some_http_service_mock.expect_request(
        "/any-method", method="*"
    ).respond_with_json({})

    # Act
    await client.post(some_http_service_mock.url_for("/any-method"))

    # Assert
    matcher = RequestMatcher("/any-method", method="GET")
    some_http_service_mock.assert_request_made(matcher, count=0)


async def test_assert_request_made_header_mismatch(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    some_http_service_mock.expect_request(
        "/hm", method="GET"
    ).respond_with_json({})

    # Act
    await client.get(
        some_http_service_mock.url_for("/hm")
    )  # no X-Secret header

    # Assert
    matcher = RequestMatcher("/hm", method="GET", headers={"X-Secret": "yes"})
    some_http_service_mock.assert_request_made(matcher, count=0)


async def test_assert_request_made_header_match(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    some_http_service_mock.expect_request(
        "/hok", method="GET"
    ).respond_with_json({})

    # Act
    await client.get(
        some_http_service_mock.url_for("/hok"), headers={"X-Trace": "abc"}
    )

    # Assert
    matcher = RequestMatcher("/hok", method="GET", headers={"X-Trace": "abc"})
    some_http_service_mock.assert_request_made(matcher, count=1)


async def test_assert_request_made_data_match(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    some_http_service_mock.expect_request(
        "/raw2", method="POST"
    ).respond_with_json({})
    await client.post(
        some_http_service_mock.url_for("/raw2"),
        data=b"\xca\xfe",
        headers={"Content-Type": "application/octet-stream"},
    )

    # Act
    ...

    # Assert
    some_http_service_mock.assert_request_made(
        RequestMatcher("/raw2", method="POST", data=b"\xca\xfe"), count=1
    )
    some_http_service_mock.assert_request_made(
        RequestMatcher("/raw2", method="POST", data=b"\x00\x00"), count=0
    )


async def test_startswith_in_assert_request_made(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    some_http_service_mock.expect_request(
        path=StartsWith("/api/"), method="GET"
    ).respond_with_json({})

    # Act
    await client.get(some_http_service_mock.url_for("/api/users"))
    await client.get(some_http_service_mock.url_for("/api/posts"))

    # Assert
    some_http_service_mock.assert_request_made(
        M(path=StartsWith("/api/"), method="GET"), count=2
    )
    some_http_service_mock.assert_request_made(
        M(path=StartsWith("/other/"), method="GET"), count=0
    )


async def test_json_contains_in_assert_request_made(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    some_http_service_mock.expect_request(
        "/ev", method="POST"
    ).respond_with_json({})

    # Act
    await client.post(
        some_http_service_mock.url_for("/ev"),
        json={"event": "click", "target": "button"},
    )
    await client.post(
        some_http_service_mock.url_for("/ev"),
        json={"event": "scroll", "target": "div"},
    )

    # Assert
    some_http_service_mock.assert_request_made(
        M("/ev", method="POST", json_contains={"event": "click"}), count=1
    )
    some_http_service_mock.assert_request_made(
        M("/ev", method="POST", json_contains={"event": "scroll"}), count=1
    )


async def test_combinator_in_assert_request_made(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    some_http_service_mock.expect_request(
        path=StartsWith("/api/"), method="GET"
    ).respond_with_json({})
    some_http_service_mock.expect_request(
        path=StartsWith("/api/"), method="POST"
    ).respond_with_json({})

    # Act
    await client.get(some_http_service_mock.url_for("/api/a"))
    await client.post(some_http_service_mock.url_for("/api/b"))

    # Assert
    get_m = M(path=StartsWith("/api/"), method="GET")
    post_m = M(path=StartsWith("/api/"), method="POST")
    some_http_service_mock.assert_request_made(get_m | post_m, count=2)


async def test_check_all_called_passes_when_all_hit(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    h1 = some_http_service_mock.expect_request("/p1", method="GET")
    h1.respond_with_json({})
    h2 = some_http_service_mock.expect_request("/p2", method="GET")
    h2.respond_with_json({})

    # Act
    await client.get(some_http_service_mock.url_for("/p1"))
    await client.get(some_http_service_mock.url_for("/p2"))

    # Assert
    some_http_service_mock.check(all_called=True)


async def test_check_all_called_fails_uncalled_permanent(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    some_http_service_mock.expect_request(
        "/called", method="GET"
    ).respond_with_json({})
    some_http_service_mock.expect_request(
        "/never", method="GET"
    ).respond_with_json({})

    # Act
    await client.get(some_http_service_mock.url_for("/called"))

    # Assert
    with pytest.raises(AssertionError, match="permanent handler"):
        some_http_service_mock.check(all_called=True)


async def test_root_path_is_handled(http_server, client):
    # Arrange
    mock = await http_server()
    mock.expect_request("/", method="GET").respond_with_json({"root": True})

    # Act
    resp = await client.get(mock.url_for("/"))

    # Assert
    assert resp.ok
    assert await resp.json() == {"root": True}


async def test_check_default_ignores_uncalled_permanent(
    some_http_service_mock: HTTPServerMock,
):
    # Act
    some_http_service_mock.expect_request(
        "/never2", method="GET"
    ).respond_with_json({})

    # Assert
    some_http_service_mock.check()


def test_expect_request_with_matcher_and_extra_method_raises():
    # Arrange
    mock = HTTPServerMock()

    # Act / Assert
    with pytest.raises(TypeError, match="matcher"):
        mock.expect_request(M(path="/api"), method="POST")


def test_expect_oneshot_with_matcher_and_extra_headers_raises():
    # Arrange
    mock = HTTPServerMock()

    # Act / Assert
    with pytest.raises(TypeError, match="matcher"):
        mock.expect_oneshot_request(
            M(path="/api"), headers={"X-Auth": "token"}
        )


def test_expect_request_with_standalone_matcher_no_extras_ok():
    """passing M() without extras should NOT raise"""
    # Arrange
    mock = HTTPServerMock()

    # Act
    handler = mock.expect_request(M(path="/api"))
    handler.respond_with_json({})


def test_expect_request_with_matcher_and_json_raises():
    """json= alongside a matcher must raise."""
    # Arrange
    mock = HTTPServerMock()

    # Act / Assert
    with pytest.raises(TypeError, match="matcher"):
        mock.expect_request(M(path="/api"), json={"key": "val"})


def test_expect_request_with_matcher_and_data_raises():
    """data= alongside a matcher must raise."""
    # Arrange
    mock = HTTPServerMock()

    # Act / Assert
    with pytest.raises(TypeError, match="matcher"):
        mock.expect_request(M(path="/api"), data=b"body")


async def test_check_error_message_names_uncalled_handler(
    some_http_service_mock: HTTPServerMock,
):
    """error must identify the uncalled handler by path"""
    # Arrange
    some_http_service_mock.expect_oneshot_request(
        "/never-called", method="GET"
    ).respond_with_json({})

    # Act
    with pytest.raises(AssertionError, match="/never-called"):
        some_http_service_mock.check()


async def test_missed_requests_logged_on_no_handler(
    client, some_http_service_mock: HTTPServerMock
):
    # Act
    await client.get(some_http_service_mock.url_for("/unknown"))
    await client.post(some_http_service_mock.url_for("/also-unknown"))

    # Assert
    missed = some_http_service_mock.missed_requests
    assert len(missed) == 2
    assert missed[0].path == "/unknown"
    assert missed[1].path == "/also-unknown"


async def test_missed_requests_cleared_by_clear(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    await client.get(some_http_service_mock.url_for("/gone"))
    assert len(some_http_service_mock.missed_requests) == 1

    # Act
    some_http_service_mock.clear()

    # Assert
    assert some_http_service_mock.missed_requests == []


async def test_matched_requests_not_in_missed_log(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    some_http_service_mock.expect_request(
        "/known", method="GET"
    ).respond_with_json({})

    # Act
    await client.get(some_http_service_mock.url_for("/known"))

    # Assert
    assert some_http_service_mock.missed_requests == []


async def test_format_matchers_shows_ordered_handlers(
    some_http_service_mock: HTTPServerMock,
):
    """format_matchers must list ORDERED handlers in its output."""
    # Arrange
    some_http_service_mock.expect_ordered_request(
        "/step1", method="POST"
    ).respond_with_json({})

    # Act
    output = some_http_service_mock.format_matchers()

    # Assert
    assert "ORDERED" in output
    assert "/step1" in output
