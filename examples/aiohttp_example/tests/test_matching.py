"""
Request matching — all the ways to describe which requests a handler catches.

By default, unmatched requests return 404 with a descriptive error message.
The more specific the matcher, the more precisely you can control routing.
"""

import re

from aiohttp import ClientSession
from async_pytest_httpserver import (
    Contains,
    HTTPServerMock,
    M,
    StartsWith,
)

from app.clients import WeatherClient


async def test_exact_path(mock: HTTPServerMock):
    """
    Default: the path must match exactly.
    """
    # Arrange
    mock.expect_request("/weather", method="GET").respond_with_json(
        {"ok": True}
    )

    # Act
    async with ClientSession() as session:
        hit = await session.get(mock.url_for("/weather"))
        miss = await session.get(mock.url_for("/Weather"))

    # Assert
    assert hit.ok
    assert miss.status == 404


async def test_regex_path(mock: HTTPServerMock):
    """
    Regex patterns match variable segments such as resource IDs.
    """
    # Arrange
    mock.expect_request(
        re.compile(r"^/users/\d+$"), method="GET"
    ).respond_with_json({"user": "found"})

    # Act
    async with ClientSession() as session:
        hit = await session.get(mock.url_for("/users/42"))
        miss = await session.get(mock.url_for("/users/abc"))

    # Assert
    assert hit.ok
    assert miss.status == 404


async def test_startswith_path(mock: HTTPServerMock):
    """
    StartsWith matches any path that begins with the given prefix.
    Useful for covering an entire API namespace with one handler.
    """
    # Arrange
    mock.expect_request(
        path=StartsWith("/api/v2/"), method="GET"
    ).respond_with_json({"version": 2})

    # Act
    async with ClientSession() as session:
        r1 = await session.get(mock.url_for("/api/v2/users"))
        r2 = await session.get(mock.url_for("/api/v2/products/5"))
        miss = await session.get(mock.url_for("/api/v1/users"))

    # Assert
    assert r1.ok
    assert r2.ok
    assert miss.status == 404


async def test_contains_path(mock: HTTPServerMock):
    """
    Contains matches any path that has the substring anywhere.
    Helpful when the resource type is embedded in a longer path.
    """
    # Arrange
    mock.expect_request(
        path=Contains("/reports/"), method="GET"
    ).respond_with_json({"report": "data"})

    # Act
    async with ClientSession() as session:
        r1 = await session.get(mock.url_for("/org/123/reports/456"))
        r2 = await session.get(mock.url_for("/v2/reports/daily"))
        miss = await session.get(mock.url_for("/org/123/users"))

    # Assert
    assert r1.ok
    assert r2.ok
    assert miss.status == 404


async def test_method_exact(mock: HTTPServerMock):
    """
    The default method is "GET". Specify method= for others.
    """
    # Arrange
    mock.expect_request("/resource", method="DELETE").respond_with_data(
        "", status=204
    )

    # Act
    async with ClientSession() as session:
        hit = await session.delete(mock.url_for("/resource"))
        miss = await session.get(mock.url_for("/resource"))

    # Assert
    assert hit.status == 204
    assert miss.status == 404


async def test_method_list(mock: HTTPServerMock):
    """
    A list of methods lets one handler cover several HTTP verbs —
    common for HEAD/GET pairs or PATCH/PUT variants.
    """
    # Arrange
    mock.expect_request("/resource", method=["GET", "HEAD"]).respond_with_json(
        {"ok": True}
    )

    # Act
    async with ClientSession() as session:
        r_get = await session.get(mock.url_for("/resource"))
        r_head = await session.head(mock.url_for("/resource"))
        r_post = await session.post(mock.url_for("/resource"))

    # Assert
    assert r_get.ok
    assert r_head.ok
    assert r_post.status == 404


async def test_method_any(mock: HTTPServerMock):
    """
    '*' matches any HTTP method.
    Useful for proxy-style handlers or catch-all fallbacks.
    """
    # Arrange
    mock.expect_request("/any", method="*").respond_with_json({"routed": True})

    # Act
    async with ClientSession() as session:
        r_get = await session.get(mock.url_for("/any"))
        r_post = await session.post(mock.url_for("/any"))
        r_put = await session.put(mock.url_for("/any"))

    # Assert
    assert r_get.ok
    assert r_post.ok
    assert r_put.ok


async def test_query_string_as_dict(
    weather_client: WeatherClient, weather_mock: HTTPServerMock
):
    """
    Dict format is order-independent — matching works regardless of
        the parameter order in the actual request URL.
    """
    # Arrange
    weather_mock.expect_request(
        "/forecast",
        method="GET",
        query_string={"city": "Berlin", "days": "3"},
    ).respond_with_json([{"day": 1}, {"day": 2}, {"day": 3}])

    # Act
    # WeatherClient sends ?city=Berlin&days=3
    forecast = await weather_client.get_forecast("Berlin", days=3)

    # Assert
    assert len(forecast) == 3


async def test_query_string_raw(mock: HTTPServerMock):
    """
    A raw string is parsed and compared parameter-by-parameter,
        so parameter order still doesn't matter.
    """
    # Arrange
    mock.expect_request(
        "/search", method="GET", query_string="sort=asc&limit=10"
    ).respond_with_json({"results": []})

    # Act
    async with ClientSession() as session:
        resp = await session.get(mock.url_for("/search?limit=10&sort=asc"))

    # Assert
    assert resp.ok


async def test_query_mismatch_returns_404(mock: HTTPServerMock):
    """
    If the query string does not match, the handler is skipped.
    """
    # Arrange
    mock.expect_request(
        "/items", method="GET", query_string={"page": "1"}
    ).respond_with_json([])

    # Act
    async with ClientSession() as session:
        resp = await session.get(mock.url_for("/items?page=2"))

    # Assert
    assert resp.status == 404


async def test_headers_exact_match(mock: HTTPServerMock):
    """
    headers= checks that all listed headers are present with exact values.
    Other headers in the request are ignored.
    """
    # Arrange
    mock.expect_request(
        "/secure", method="GET", headers={"X-Api-Key": "secret123"}
    ).respond_with_json({"data": "private"})

    # Act
    async with ClientSession() as session:
        hit = await session.get(
            mock.url_for("/secure"), headers={"X-Api-Key": "secret123"}
        )
        miss = await session.get(
            mock.url_for("/secure"), headers={"X-Api-Key": "wrong"}
        )

    # Assert
    assert hit.ok
    assert miss.status == 404


async def test_header_value_matcher(mock: HTTPServerMock):
    """
    header_value_matcher is a callable (name, actual, expected) -> bool
        for custom comparison logic — e.g. "starts with Bearer".
    """

    # Arrange
    def bearer_prefix(name, actual, expected):
        return actual.startswith(expected)

    mock.expect_request(
        "/auth",
        method="GET",
        headers={"Authorization": "Bearer "},
        header_value_matcher=bearer_prefix,
    ).respond_with_json({"user": "alice"})

    # Act
    async with ClientSession() as session:
        hit = await session.get(
            mock.url_for("/auth"),
            headers={"Authorization": "Bearer abc123token"},
        )
        miss = await session.get(
            mock.url_for("/auth"),
            headers={"Authorization": "Basic dXNlcjpwYXNz"},
        )

    # Assert
    assert hit.ok
    assert miss.status == 404


async def test_json_exact_match(mock: HTTPServerMock):
    """
    json= requires the request body to equal the expected dict exactly.
    Useful when you need to assert a specific payload is sent.
    """
    # Arrange
    mock.expect_request(
        "/users", method="POST", json={"name": "Alice", "role": "admin"}
    ).respond_with_json({"id": 1})

    # Act
    async with ClientSession() as session:
        hit = await session.post(
            mock.url_for("/users"),
            json={"name": "Alice", "role": "admin"},
        )
        miss = await session.post(
            mock.url_for("/users"),
            json={"name": "Alice"},  # missing "role"
        )

    # Assert
    assert hit.ok
    assert miss.status == 404


async def test_json_contains_partial_match(mock: HTTPServerMock):
    """
    json_contains= does a recursive subset check — only the listed
        keys must be present with the given values. Extra keys are allowed.
    Use this when you only care about specific fields.
    """
    # Arrange
    mock.expect_request(
        "/events",
        method="POST",
        json_contains={"type": "click"},
    ).respond_with_json({"ok": True})

    # Act
    async with ClientSession() as session:
        # Request body has extra fields — still matches
        hit = await session.post(
            mock.url_for("/events"),
            json={"type": "click", "target": "button", "ts": 1234},
        )
        miss = await session.post(
            mock.url_for("/events"),
            json={"type": "scroll", "target": "div"},  # wrong type
        )

    # Assert
    assert hit.ok
    assert miss.status == 404


async def test_data_bytes_match(mock: HTTPServerMock):
    """
    data= matches the raw request body as bytes.
    Use for binary protocols or non-JSON payloads.
    """
    # Arrange
    mock.expect_request(
        "/upload",
        method="POST",
        data=b"\xff\xd8\xff",  # JPEG magic bytes
    ).respond_with_data("", status=204)

    # Act
    async with ClientSession() as session:
        hit = await session.post(
            mock.url_for("/upload"),
            data=b"\xff\xd8\xff",
            headers={"Content-Type": "application/octet-stream"},
        )
        miss = await session.post(
            mock.url_for("/upload"),
            data=b"\x89\x50\x4e\x47",  # PNG magic bytes
            headers={"Content-Type": "application/octet-stream"},
        )

    # Assert
    assert hit.status == 204
    assert miss.status == 404


async def test_or_combinator(mock: HTTPServerMock):
    """
    M(…) | M(…) matches when EITHER condition is true.
    One handler can cover multiple paths or methods.
    """
    # Arrange
    mock.expect_request(
        M(path="/api/v1", method="GET") | M(path="/api/v2", method="GET")
    ).respond_with_json({"supported": True})

    # Act
    async with ClientSession() as session:
        r1 = await session.get(mock.url_for("/api/v1"))
        r2 = await session.get(mock.url_for("/api/v2"))
        miss = await session.get(mock.url_for("/api/v3"))

    # Assert
    assert r1.ok
    assert r2.ok
    assert miss.status == 404


async def test_and_combinator(mock: HTTPServerMock):
    """
    M(…) & M(…) matches only when BOTH conditions are true.
    Here: path must start with /api/ AND the X-Auth header must be present.
    """
    # Arrange
    mock.expect_request(
        M(path=StartsWith("/api/"), method="GET")
        & M(headers={"X-Auth": "token"})
    ).respond_with_json({"data": "private"})

    # Act
    async with ClientSession() as session:
        # Both conditions satisfied
        hit = await session.get(
            mock.url_for("/api/users"), headers={"X-Auth": "token"}
        )
        # Path matches but header missing
        miss_header = await session.get(mock.url_for("/api/users"))
        # Header present but path doesn't match
        miss_path = await session.get(
            mock.url_for("/public/data"), headers={"X-Auth": "token"}
        )

    # Assert
    assert hit.ok
    assert miss_header.status == 404
    assert miss_path.status == 404


async def test_not_combinator(mock: HTTPServerMock):
    """
    ~M(…) inverts the match — the handler responds to everything
    EXCEPT what the inner matcher describes.
    Handy for health-check exclusions.
    """
    # Arrange
    mock.expect_request(
        ~M(path=StartsWith("/health")), method="GET"
    ).respond_with_json({"payload": True})

    # Act
    async with ClientSession() as session:
        hit = await session.get(mock.url_for("/api/data"))
        miss = await session.get(mock.url_for("/health"))
        miss_live = await session.get(mock.url_for("/health/live"))

    # Assert
    assert hit.ok
    assert miss.status == 404
    assert miss_live.status == 404
