import pytest

from async_pytest_httpserver import (
    ConflictError,
    ConflictPolicy,
    M,
    StartsWith,
)


async def test_last_wins_permanent(http_server, client):
    # Arrange
    mock = await http_server(conflict_policy=ConflictPolicy.LAST_WINS)
    mock.expect_request("/foo", method="GET").respond_with_data("first")
    mock.expect_request("/foo", method="GET").respond_with_data("second")

    # Act
    resp = await client.get(mock.url_for("/foo"))

    # Assert
    assert await resp.text() == "second"


async def test_first_wins_permanent(http_server, client):
    # Arrange
    mock = await http_server(conflict_policy=ConflictPolicy.FIRST_WINS)
    mock.expect_request("/foo", method="GET").respond_with_data("first")
    mock.expect_request("/foo", method="GET").respond_with_data("second")

    # Act
    resp = await client.get(mock.url_for("/foo"))

    # Assert
    assert await resp.text() == "first"


async def test_last_wins_oneshot(http_server, client):
    # Arrange
    mock = await http_server(conflict_policy=ConflictPolicy.LAST_WINS)
    mock.expect_oneshot_request("/foo", method="GET").respond_with_data(
        "first"
    )
    mock.expect_oneshot_request("/foo", method="GET").respond_with_data(
        "second"
    )

    # Act
    resp = await client.get(mock.url_for("/foo"))

    # Assert
    assert await resp.text() == "second"


async def test_default_policy_is_last_wins(http_server, client):
    # Arrange
    mock = await http_server()
    mock.expect_request("/foo", method="GET").respond_with_data("first")
    mock.expect_request("/foo", method="GET").respond_with_data("second")

    # Act
    resp = await client.get(mock.url_for("/foo"))

    # Assert
    assert await resp.text() == "second"


def test_overlap_same_path_and_method():
    assert M("/foo", "GET").could_overlap(M("/foo", "GET")) is True


def test_overlap_different_exact_paths():
    assert M("/foo", "GET").could_overlap(M("/bar", "GET")) is False


def test_overlap_different_methods():
    assert M("/foo", "GET").could_overlap(M("/foo", "POST")) is False


def test_overlap_starts_with_matches_exact_path():
    a = M(StartsWith("/api"), "GET")
    b = M("/api/users", "GET")
    assert a.could_overlap(b) is True


def test_overlap_starts_with_no_match_exact_path():
    a = M(StartsWith("/api"), "GET")
    b = M("/other", "GET")
    assert a.could_overlap(b) is False


def test_overlap_starts_with_vs_starts_with_one_prefix():
    a = M(StartsWith("/api"), "GET")
    b = M(StartsWith("/api/users"), "GET")
    assert a.could_overlap(b) is True


def test_overlap_starts_with_vs_starts_with_disjoint():
    a = M(StartsWith("/api"), "GET")
    b = M(StartsWith("/other"), "GET")
    assert a.could_overlap(b) is False


def test_overlap_different_json():
    a = M("/foo", "POST", json={"key": "v1"})
    b = M("/foo", "POST", json={"key": "v2"})
    assert a.could_overlap(b) is False


def test_overlap_same_json():
    a = M("/foo", "POST", json={"key": "val"})
    b = M("/foo", "POST", json={"key": "val"})
    assert a.could_overlap(b) is True


def test_overlap_different_query_string():
    a = M("/foo", "GET", query_string={"q": "a"})
    b = M("/foo", "GET", query_string={"q": "b"})
    assert a.could_overlap(b) is False


def test_overlap_different_headers():
    a = M("/foo", "GET", headers={"X-Token": "abc"})
    b = M("/foo", "GET", headers={"X-Token": "xyz"})
    assert a.could_overlap(b) is False


def test_overlap_wildcard_method():
    a = M("/foo", "*")
    b = M("/foo", "POST")
    assert a.could_overlap(b) is True


def test_overlap_composite_matcher_is_conservative():
    composite = M("/foo") & M("/bar")
    plain = M("/foo", "GET")
    assert composite.could_overlap(plain) is True


async def test_error_exact_duplicate(http_server):
    mock = await http_server(conflict_policy=ConflictPolicy.ERROR)
    mock.expect_request("/foo", method="GET").respond_with_data("ok")

    with pytest.raises(ConflictError):
        mock.expect_request("/foo", method="GET").respond_with_data("dup")


async def test_error_starts_with_overlap(http_server):
    mock = await http_server(conflict_policy=ConflictPolicy.ERROR)
    mock.expect_request(StartsWith("/api"), method="GET").respond_with_data(
        "ok"
    )

    with pytest.raises(ConflictError):
        mock.expect_request("/api/users", method="GET").respond_with_data(
            "dup"
        )


async def test_error_no_conflict_different_method(http_server):
    mock = await http_server(conflict_policy=ConflictPolicy.ERROR)
    mock.expect_request("/foo", method="GET").respond_with_data("get")

    mock.expect_request("/foo", method="POST").respond_with_data("post")


async def test_error_no_conflict_different_json(http_server):
    mock = await http_server(conflict_policy=ConflictPolicy.ERROR)
    mock.expect_request(
        "/foo", method="POST", json={"k": "v1"}
    ).respond_with_data("ok")

    mock.expect_request(
        "/foo", method="POST", json={"k": "v2"}
    ).respond_with_data("ok2")


async def test_error_no_conflict_different_query(http_server):
    mock = await http_server(conflict_policy=ConflictPolicy.ERROR)
    mock.expect_request(
        "/foo", method="GET", query_string={"q": "a"}
    ).respond_with_data("ok")

    mock.expect_request(
        "/foo", method="GET", query_string={"q": "b"}
    ).respond_with_data("ok2")
