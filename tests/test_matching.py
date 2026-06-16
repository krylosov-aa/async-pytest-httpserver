import re

import pytest

from async_pytest_httpserver import (
    Contains,
    HTTPServerMock,
    M,
    StartsWith,
)


async def test_match_query_string_dict(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    handler = some_http_service_mock.expect_request(
        "/search", method="GET", query_string={"q": "cats", "page": "1"}
    )
    handler.respond_with_json({"hits": 10})

    # Act
    resp = await client.get(
        some_http_service_mock.url_for("/search?page=1&q=cats")
    )

    # Assert
    assert resp.ok
    handler.call_log.assert_called_once()


async def test_match_query_string_str(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    handler = some_http_service_mock.expect_request(
        "/items", method="GET", query_string="sort=asc&limit=10"
    )
    handler.respond_with_json([])

    # Act
    resp = await client.get(
        some_http_service_mock.url_for("/items?limit=10&sort=asc")
    )

    # Assert
    assert resp.ok
    handler.call_log.assert_called_once()


async def test_match_headers(client, some_http_service_mock: HTTPServerMock):
    # Arrange
    handler = some_http_service_mock.expect_request(
        "/secure",
        method="GET",
        headers={"X-Token": "secret"},
    )
    handler.respond_with_json({"ok": True})

    # Act
    resp = await client.get(
        some_http_service_mock.url_for("/secure"),
        headers={"X-Token": "secret"},
    )

    # Assert
    assert resp.ok
    handler.call_log.assert_called_once()


async def test_no_match_on_wrong_header(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    some_http_service_mock.expect_request(
        "/secure", method="GET", headers={"X-Token": "secret"}
    ).respond_with_json({"ok": True})

    # Act
    resp = await client.get(
        some_http_service_mock.url_for("/secure"),
        headers={"X-Token": "wrong"},
    )

    # Assert
    assert resp.status == 404


async def test_match_json_body(client, some_http_service_mock: HTTPServerMock):
    # Arrange
    handler = some_http_service_mock.expect_request(
        "/create", method="POST", json={"name": "alice"}
    )
    handler.respond_with_json({"id": 1})

    # Act
    resp = await client.post(
        some_http_service_mock.url_for("/create"), json={"name": "alice"}
    )

    # Assert
    assert resp.ok
    handler.call_log.assert_called_once()


async def test_no_match_on_wrong_json(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    some_http_service_mock.expect_request(
        "/create", method="POST", json={"name": "alice"}
    ).respond_with_json({"id": 1})

    # Act
    resp = await client.post(
        some_http_service_mock.url_for("/create"), json={"name": "bob"}
    )

    # Assert
    assert resp.status == 404


async def test_match_regex_path(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    handler = some_http_service_mock.expect_request(
        re.compile(r"^/users/\d+$"), method="GET"
    )
    handler.respond_with_json({"user": "found"})

    # Act
    resp = await client.get(some_http_service_mock.url_for("/users/42"))

    # Assert
    assert resp.ok
    handler.call_log.assert_called_once()


async def test_header_value_matcher_custom(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    def prefix_matcher(name: str, actual: str, expected: str) -> bool:
        return actual.startswith(expected)

    handler = some_http_service_mock.expect_request(
        "/auth",
        method="GET",
        headers={"Authorization": "Bearer "},
        header_value_matcher=prefix_matcher,
    )
    handler.respond_with_json({"ok": True})

    # Act
    resp = await client.get(
        some_http_service_mock.url_for("/auth"),
        headers={"Authorization": "Bearer abc123"},
    )

    # Assert
    assert resp.ok
    handler.call_log.assert_called_once()


async def test_match_data_bytes(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    handler = some_http_service_mock.expect_request(
        "/raw", method="POST", data=b"\xde\xad"
    )
    handler.respond_with_json({"matched": True})

    # Act
    resp = await client.post(
        some_http_service_mock.url_for("/raw"),
        data=b"\xde\xad",
        headers={"Content-Type": "application/octet-stream"},
    )
    no_match = await client.post(
        some_http_service_mock.url_for("/raw"),
        data=b"\xff\xff",
        headers={"Content-Type": "application/octet-stream"},
    )

    # Assert
    assert resp.ok
    assert no_match.status == 404


async def test_match_data_string(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    handler = some_http_service_mock.expect_request(
        "/str", method="POST", data="hello"
    )
    handler.respond_with_json({})

    # Act
    resp = await client.post(
        some_http_service_mock.url_for("/str"),
        data="hello",
        headers={"Content-Type": "text/plain"},
    )

    # Assert
    assert resp.ok
    handler.call_log.assert_called_once()


async def test_method_any_matches_any_method(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    handler = some_http_service_mock.expect_request("/any", method="*")
    handler.respond_with_json({})

    # Act
    r_get = await client.get(some_http_service_mock.url_for("/any"))
    r_post = await client.post(some_http_service_mock.url_for("/any"))
    r_delete = await client.delete(some_http_service_mock.url_for("/any"))

    # Assert
    assert r_get.ok
    assert r_post.ok
    assert r_delete.ok
    handler.call_log.assert_call_count(3)


async def test_wrong_method_returns_404(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    some_http_service_mock.expect_request(
        "/get-only", method="GET"
    ).respond_with_json({})

    # Act
    resp = await client.post(some_http_service_mock.url_for("/get-only"))

    # Assert
    assert resp.status == 404


async def test_match_query_string_subset(
    client, some_http_service_mock: HTTPServerMock
):
    """
    handler requires only page=1, extra params should be ignored
    """
    # Arrange
    handler = some_http_service_mock.expect_request(
        "/results", method="GET", query_string={"page": "1"}
    )
    handler.respond_with_json({"ok": True})

    # Act
    resp = await client.get(
        some_http_service_mock.url_for("/results?page=1&limit=20&sort=asc")
    )
    miss = await client.get(some_http_service_mock.url_for("/results?page=2"))

    # Assert
    assert resp.ok
    assert miss.status == 404
    handler.call_log.assert_called_once()


async def test_wrong_query_returns_404(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    some_http_service_mock.expect_request(
        "/paged", method="GET", query_string={"page": "1"}
    ).respond_with_json({})

    # Act
    resp = await client.get(some_http_service_mock.url_for("/paged?page=2"))

    # Assert
    assert resp.status == 404


async def test_json_matcher_invalid_body_returns_404(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    some_http_service_mock.expect_request(
        "/jm2", method="POST", json={"key": "val"}
    ).respond_with_json({})

    # Act
    resp = await client.post(
        some_http_service_mock.url_for("/jm2"),
        data=b"not-valid-json",
        headers={"Content-Type": "application/json"},
    )

    # Assert
    assert resp.status == 404


async def test_invalid_json_body_stored_as_raw(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    handler = some_http_service_mock.expect_request(
        "/bad-json2", method="POST"
    )
    handler.respond_with_json({})

    # Act
    await client.post(
        some_http_service_mock.url_for("/bad-json2"),
        data=b"\xff\xfe\x00",
        headers={"Content-Type": "application/json"},
    )

    # Assert
    call = handler.call_log[0]
    assert call.json is None
    assert call.data == b"\xff\xfe\x00"


async def test_startswith_matches_prefix(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    handler = some_http_service_mock.expect_request(
        path=StartsWith("/api/"), method="GET"
    )
    handler.respond_with_json({"ok": True})

    # Act
    r1 = await client.get(some_http_service_mock.url_for("/api/users"))
    r2 = await client.get(some_http_service_mock.url_for("/api/products"))
    r_miss = await client.get(some_http_service_mock.url_for("/other/path"))

    # Assert
    assert r1.ok
    assert r2.ok
    assert r_miss.status == 404
    handler.call_log.assert_call_count(2)


async def test_contains_matches_substring(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    handler = some_http_service_mock.expect_request(
        path=Contains("/users/"), method="GET"
    )
    handler.respond_with_json({"found": True})

    # Act
    r1 = await client.get(some_http_service_mock.url_for("/api/users/42"))
    r2 = await client.get(
        some_http_service_mock.url_for("/v2/users/99/profile")
    )
    r_miss = await client.get(some_http_service_mock.url_for("/api/products"))

    # Assert
    assert r1.ok
    assert r2.ok
    assert r_miss.status == 404
    handler.call_log.assert_call_count(2)


async def test_method_list_matches_multiple(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    handler = some_http_service_mock.expect_request(
        "/resource", method=["GET", "HEAD"]
    )
    handler.respond_with_json({"ok": True})

    # Act
    r_get = await client.get(some_http_service_mock.url_for("/resource"))
    r_head = await client.head(some_http_service_mock.url_for("/resource"))
    r_post = await client.post(some_http_service_mock.url_for("/resource"))

    # Assert
    assert r_get.ok
    assert r_head.ok
    assert r_post.status == 404
    handler.call_log.assert_call_count(2)


async def test_json_contains_matches_subset(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    handler = some_http_service_mock.expect_request(
        "/users",
        method="POST",
        json_contains={"user": {"name": "Alice"}},
    )
    handler.respond_with_json({"created": True})

    # Act
    resp = await client.post(
        some_http_service_mock.url_for("/users"),
        json={"user": {"name": "Alice", "role": "admin"}, "meta": {"ts": 1}},
    )
    miss = await client.post(
        some_http_service_mock.url_for("/users"),
        json={"user": {"name": "Bob"}},
    )

    # Assert
    assert resp.ok
    assert miss.status == 404
    handler.call_log.assert_called_once()


async def test_json_contains_nested(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    handler = some_http_service_mock.expect_request(
        "/data",
        method="POST",
        json_contains={"level1": {"level2": {"key": "val"}}},
    )
    handler.respond_with_json({})

    # Act
    resp = await client.post(
        some_http_service_mock.url_for("/data"),
        json={"level1": {"level2": {"key": "val", "extra": 1}}, "other": 2},
    )

    # Assert
    assert resp.ok
    handler.call_log.assert_called_once()


async def test_or_combinator_matches_either(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    handler = some_http_service_mock.expect_request(
        M(path="/api/v1", method="GET") | M(path="/api/v2", method="GET")
    )
    handler.respond_with_json({"version": "ok"})

    # Act
    r1 = await client.get(some_http_service_mock.url_for("/api/v1"))
    r2 = await client.get(some_http_service_mock.url_for("/api/v2"))
    r_miss = await client.get(some_http_service_mock.url_for("/api/v3"))

    # Assert
    assert r1.ok
    assert r2.ok
    assert r_miss.status == 404
    handler.call_log.assert_call_count(2)


async def test_and_combinator_requires_both(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    handler = some_http_service_mock.expect_request(
        M(path=StartsWith("/api/"), method="GET")
        & M(headers={"X-Auth": "token"})
    )
    handler.respond_with_json({"ok": True})

    # Act
    r_ok = await client.get(
        some_http_service_mock.url_for("/api/users"),
        headers={"X-Auth": "token"},
    )
    r_no_header = await client.get(
        some_http_service_mock.url_for("/api/users")
    )
    r_wrong_path = await client.get(
        some_http_service_mock.url_for("/other"),
        headers={"X-Auth": "token"},
    )

    # Assert
    assert r_ok.ok
    assert r_no_header.status == 404
    assert r_wrong_path.status == 404
    handler.call_log.assert_called_once()


async def test_not_combinator_inverts_match(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    handler = some_http_service_mock.expect_request(
        ~M(path=StartsWith("/health")), method="GET"
    )
    handler.respond_with_json({"data": True})

    # Act
    r_api = await client.get(some_http_service_mock.url_for("/api/users"))
    r_health = await client.get(some_http_service_mock.url_for("/health"))

    # Assert
    assert r_api.ok
    assert r_health.status == 404
    handler.call_log.assert_called_once()


async def test_combined_and_or(client, some_http_service_mock: HTTPServerMock):
    # Arrange
    handler = some_http_service_mock.expect_request(
        (M(path="/v1", method="*") | M(path="/v2", method="*"))
        & M(method="POST")
    )
    handler.respond_with_json({"ok": True})

    # Act
    r1 = await client.post(some_http_service_mock.url_for("/v1"))
    r2 = await client.post(some_http_service_mock.url_for("/v2"))
    r3 = await client.get(some_http_service_mock.url_for("/v1"))  # GET — miss
    r4 = await client.post(
        some_http_service_mock.url_for("/v3")
    )  # wrong path — miss

    # Assert
    assert r1.ok
    assert r2.ok
    assert r3.status == 404
    assert r4.status == 404
    handler.call_log.assert_call_count(2)


async def test_assert_request_made_data_matches_text_plain_body(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    some_http_service_mock.expect_request(
        "/txt-data", method="POST"
    ).respond_with_json({})

    # Act
    await client.post(
        some_http_service_mock.url_for("/txt-data"),
        data="hello world",
        headers={"Content-Type": "text/plain"},
    )

    # Assert
    some_http_service_mock.assert_request_made(
        M("/txt-data", method="POST", data="hello world"), count=1
    )
    some_http_service_mock.assert_request_made(
        M("/txt-data", method="POST", data="wrong body"), count=0
    )


def test_repr_shows_all_matcher_criteria():
    # Arrange
    matcher = M(
        "/api",
        method="POST",
        headers={"X-Auth": "token"},
        json={"key": "val"},
        query_string={"p": "1"},
    )

    # Act
    r = repr(matcher)

    # Assert
    assert "headers=" in r
    assert "json=" in r
    assert "query_string=" in r
    assert "/api" in r
    assert "POST" in r


def test_repr_shows_json_contains_and_data():
    # Act
    m_jc = M("/x", json_contains={"k": 1})
    m_data = M("/y", data=b"\xde\xad")

    # Assert
    assert "json_contains=" in repr(m_jc)
    assert "data=" in repr(m_data)


def test_combinators_repr():
    """__repr__ of _And, _Or, _Not and path lookups must be well-formed."""
    # Act
    m_and = M(path="/a") & M(path="/b")
    m_or = M(path="/a") | M(path="/b")
    m_not = ~M(path="/a")

    # Assert
    assert "&" in repr(m_and)
    assert "|" in repr(m_or)
    assert "~" in repr(m_not)
    assert repr(StartsWith("/x")) == "StartsWith('/x')"
    assert repr(Contains("/x")) == "Contains('/x')"


async def test_and_combinator_in_assert_request_made(
    client, some_http_service_mock: HTTPServerMock
):
    """_And.matches_call_info must be exercised via assert_request_made."""
    # Arrange
    some_http_service_mock.expect_request(
        path=StartsWith("/api/"), method="POST"
    ).respond_with_json({})

    # Act
    await client.post(
        some_http_service_mock.url_for("/api/users"),
        headers={"X-Auth": "token"},
    )
    await client.post(some_http_service_mock.url_for("/api/users"))

    # Assert
    # Both conditions must match
    some_http_service_mock.assert_request_made(
        M(path=StartsWith("/api/"), method="POST")
        & M(method="POST", headers={"X-Auth": "token"}),
        count=1,
    )
    # Only path matches, header does not
    some_http_service_mock.assert_request_made(
        M(path=StartsWith("/api/"), method="POST")
        & M(method="POST", headers={"X-Auth": "wrong"}),
        count=0,
    )


async def test_not_combinator_in_assert_request_made(
    client, some_http_service_mock: HTTPServerMock
):
    """_Not.matches_call_info must be exercised via assert_request_made."""
    # Arrange
    some_http_service_mock.expect_request(
        method="*", path=StartsWith("/")
    ).respond_with_json({})

    # Act
    await client.get(some_http_service_mock.url_for("/health"))
    await client.get(some_http_service_mock.url_for("/api/users"))

    # Assert
    some_http_service_mock.assert_request_made(~M(path="/health"), count=1)
    some_http_service_mock.assert_request_made(
        ~M(path="/nonexistent"), count=2
    )


async def test_json_contains_matcher_invalid_json_body(
    client, some_http_service_mock: HTTPServerMock
):
    """json_contains= must not crash on invalid JSON body."""
    # Arrange
    some_http_service_mock.expect_request(
        "/jci", method="POST", json_contains={"key": "val"}
    ).respond_with_json({})

    # Act
    resp = await client.post(
        some_http_service_mock.url_for("/jci"),
        data=b"not-json",
        headers={"Content-Type": "application/json"},
    )

    # Assert
    assert resp.status == 404


async def test_assert_request_made_data_no_body_no_match(
    client, some_http_service_mock: HTTPServerMock
):
    """data= matcher on a request with no body must return count=0."""
    # Arrange
    some_http_service_mock.expect_request(
        "/nobod", method="GET"
    ).respond_with_json({})

    # Act
    await client.get(some_http_service_mock.url_for("/nobod"))

    # Assert
    some_http_service_mock.assert_request_made(
        M("/nobod", method="GET", data=b"x"), count=0
    )


def test_matcher_json_and_data_raises():
    """Passing both json= and data= to M() must raise TypeError."""
    with pytest.raises(TypeError, match="json and data"):
        M("/api", method="POST", json={"key": "val"}, data=b"raw")


def test_matcher_json_and_json_contains_raises():
    """Passing both json= and json_contains= to M() must raise TypeError."""
    with pytest.raises(TypeError, match="json and json_contains"):
        M(
            "/api",
            method="POST",
            json={"a": 1},
            json_contains={"b": 2},
        )


def test_matcher_json_contains_and_data_raises():
    """Passing both json_contains= and data= to M() must raise TypeError."""
    with pytest.raises(TypeError, match="json_contains and data"):
        M("/api", method="POST", json_contains={"a": 1}, data=b"raw")
