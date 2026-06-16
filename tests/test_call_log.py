import pytest

from async_pytest_httpserver import HTTPServerMock


async def test_call_log_assert_not_called(
    some_http_service_mock: HTTPServerMock,
):
    # Arrange
    handler = some_http_service_mock.expect_request("/unused", method="GET")
    handler.respond_with_json({})

    # Act
    ...

    # Assert
    handler.call_log.assert_not_called()


async def test_call_log_assert_call_count(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    handler = some_http_service_mock.expect_request("/hit", method="GET")
    handler.respond_with_json({})

    # Act
    await client.get(some_http_service_mock.url_for("/hit"))
    await client.get(some_http_service_mock.url_for("/hit"))

    # Assert
    handler.call_log.assert_call_count(2)


async def test_call_log_assert_called_with_query(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    handler = some_http_service_mock.expect_request("/q", method="GET")
    handler.respond_with_json({})

    # Act
    await client.get(some_http_service_mock.url_for("/q?foo=bar"))
    # Assert
    handler.call_log.assert_called_with(query={"foo": "bar"})


async def test_call_log_assert_called_with_headers(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    handler = some_http_service_mock.expect_request("/h", method="GET")
    handler.respond_with_json({})

    # Act
    await client.get(
        some_http_service_mock.url_for("/h"), headers={"X-Custom": "val"}
    )

    # Assert
    handler.call_log.assert_called_with(headers={"X-Custom": "val"})


async def test_assert_called_with_first_call(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    handler = some_http_service_mock.expect_request("/seq", method="POST")
    handler.respond_with_json({})

    # Act
    await client.post(some_http_service_mock.url_for("/seq"), json={"n": 1})
    await client.post(some_http_service_mock.url_for("/seq"), json={"n": 2})

    # Assert
    handler.call_log.assert_called_with(call_index=0, json={"n": 1})
    handler.call_log.assert_called_with(call_index=1, json={"n": 2})
    handler.call_log.assert_called_with(json={"n": 2})  # default: last


async def test_call_log_len(client, some_http_service_mock: HTTPServerMock):
    # Arrange
    handler = some_http_service_mock.expect_request("/n", method="GET")
    handler.respond_with_json({})

    # Act
    await client.get(some_http_service_mock.url_for("/n"))
    await client.get(some_http_service_mock.url_for("/n"))

    # Assert
    assert len(handler.call_log) == 2


async def test_call_log_getitem(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    handler = some_http_service_mock.expect_request("/idx", method="POST")
    handler.respond_with_json({})

    # Act
    await client.post(some_http_service_mock.url_for("/idx"), json={"i": 0})
    await client.post(some_http_service_mock.url_for("/idx"), json={"i": 1})

    # Assert
    assert handler.call_log[0].json == {"i": 0}
    assert handler.call_log[1].json == {"i": 1}


async def test_call_log_iter(client, some_http_service_mock: HTTPServerMock):
    # Arrange
    handler = some_http_service_mock.expect_request("/it", method="POST")
    handler.respond_with_json({})

    # Act
    await client.post(some_http_service_mock.url_for("/it"), json={"x": 1})
    await client.post(some_http_service_mock.url_for("/it"), json={"x": 2})

    # Assert
    payloads = [call.json for call in handler.call_log]
    assert payloads == [{"x": 1}, {"x": 2}]


async def test_assert_called_once_fails_when_not_called(
    some_http_service_mock: HTTPServerMock,
):
    # Arrange
    handler = some_http_service_mock.expect_request("/nc", method="GET")
    handler.respond_with_json({})

    # Act
    ...

    # Assert
    with pytest.raises(AssertionError, match="Expected 1 call"):
        handler.call_log.assert_called_once()


async def test_assert_called_once_fails_on_multi_calls(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    handler = some_http_service_mock.expect_request("/mc", method="GET")
    handler.respond_with_json({})

    # Act
    await client.get(some_http_service_mock.url_for("/mc"))
    await client.get(some_http_service_mock.url_for("/mc"))

    # Assert
    with pytest.raises(AssertionError, match="Expected 1 call"):
        handler.call_log.assert_called_once()


async def test_assert_not_called_fails_when_called(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    handler = some_http_service_mock.expect_request("/was", method="GET")
    handler.respond_with_json({})

    # Act
    await client.get(some_http_service_mock.url_for("/was"))

    # Assert
    with pytest.raises(AssertionError, match="Expected 0 calls"):
        handler.call_log.assert_not_called()


async def test_assert_call_count_fails_on_mismatch(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    handler = some_http_service_mock.expect_request("/cnt", method="GET")
    handler.respond_with_json({})

    # Act
    await client.get(some_http_service_mock.url_for("/cnt"))

    # Assert
    with pytest.raises(AssertionError, match="Expected 3 call"):
        handler.call_log.assert_call_count(3)


async def test_assert_called_with_fails_when_no_calls(
    some_http_service_mock: HTTPServerMock,
):
    # Arrange
    handler = some_http_service_mock.expect_request("/empty", method="GET")
    handler.respond_with_json({})

    # Act
    ...

    # Assert
    with pytest.raises(AssertionError, match="No calls recorded"):
        handler.call_log.assert_called_with(json={"x": 1})


async def test_assert_called_with_out_of_range_index(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    handler = some_http_service_mock.expect_request("/oor", method="GET")
    handler.respond_with_json({})

    # Act
    await client.get(some_http_service_mock.url_for("/oor"))

    # Assert
    with pytest.raises(AssertionError, match="out of range"):
        handler.call_log.assert_called_with(call_index=5)


async def test_assert_called_with_fails_on_wrong_json(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    handler = some_http_service_mock.expect_request("/wj", method="POST")
    handler.respond_with_json({})

    # Act
    await client.post(
        some_http_service_mock.url_for("/wj"), json={"got": "this"}
    )

    # Assert
    with pytest.raises(AssertionError, match="Expected json"):
        handler.call_log.assert_called_with(json={"want": "that"})


async def test_assert_called_with_fails_on_wrong_text(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    handler = some_http_service_mock.expect_request("/wt", method="POST")
    handler.respond_with_json({})

    # Act
    await client.post(
        some_http_service_mock.url_for("/wt"),
        data="actual",
        headers={"Content-Type": "text/plain"},
    )

    # Assert
    with pytest.raises(AssertionError, match="Expected text"):
        handler.call_log.assert_called_with(text="expected")


async def test_assert_called_with_fails_on_wrong_header(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    handler = some_http_service_mock.expect_request("/wh", method="GET")
    handler.respond_with_json({})

    # Act
    await client.get(
        some_http_service_mock.url_for("/wh"), headers={"X-Got": "this"}
    )

    # Assert
    with pytest.raises(AssertionError, match="Expected header"):
        handler.call_log.assert_called_with(headers={"X-Got": "other"})


async def test_assert_called_with_fails_on_wrong_query(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    handler = some_http_service_mock.expect_request("/wq", method="GET")
    handler.respond_with_json({})

    # Act
    await client.get(some_http_service_mock.url_for("/wq?a=1"))

    # Assert
    with pytest.raises(AssertionError, match="Expected query"):
        handler.call_log.assert_called_with(query={"a": "2"})


async def test_text_body_captured(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    handler = some_http_service_mock.expect_request("/txt", method="POST")
    handler.respond_with_json({})

    # Act
    await client.post(
        some_http_service_mock.url_for("/txt"),
        data="hello world",
        headers={"Content-Type": "text/plain"},
    )

    # Assert
    call = handler.call_log[0]
    assert call.text == "hello world"
    assert call.json is None
    assert call.data is None


async def test_binary_body_captured(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    handler = some_http_service_mock.expect_request("/bin", method="POST")
    handler.respond_with_json({})

    # Act
    await client.post(
        some_http_service_mock.url_for("/bin"),
        data=b"\x00\x01\x02",
        headers={"Content-Type": "application/octet-stream"},
    )

    # Assert
    call = handler.call_log[0]
    assert call.data == b"\x00\x01\x02"
    assert call.json is None
    assert call.text is None


async def test_empty_body_all_none(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    handler = some_http_service_mock.expect_request("/noBody", method="GET")
    handler.respond_with_json({})

    # Act
    await client.get(some_http_service_mock.url_for("/noBody"))

    # Assert
    call = handler.call_log[0]
    assert call.json is None
    assert call.text is None
    assert call.data is None


async def test_assert_called_passes_when_called(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    handler = some_http_service_mock.expect_request("/ac", method="GET")
    handler.respond_with_json({})

    # Act
    await client.get(some_http_service_mock.url_for("/ac"))
    await client.get(some_http_service_mock.url_for("/ac"))

    # Assert — passes for 2 calls (unlike assert_called_once)
    handler.call_log.assert_called()


async def test_assert_called_fails_when_not_called(
    some_http_service_mock: HTTPServerMock,
):
    # Arrange
    handler = some_http_service_mock.expect_request("/nc2", method="GET")
    handler.respond_with_json({})

    # Act
    ...

    # Assert
    with pytest.raises(AssertionError, match="at least 1 call"):
        handler.call_log.assert_called()


async def test_call_log_last_returns_last_call(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    handler = some_http_service_mock.expect_request("/last", method="POST")
    handler.respond_with_json({})

    # Act
    await client.post(some_http_service_mock.url_for("/last"), json={"n": 1})
    await client.post(some_http_service_mock.url_for("/last"), json={"n": 2})

    # Assert
    assert handler.call_log.last.json == {"n": 2}


async def test_call_log_last_raises_when_empty(
    some_http_service_mock: HTTPServerMock,
):
    # Arrange
    handler = some_http_service_mock.expect_request("/empty2", method="GET")
    handler.respond_with_json({})

    with pytest.raises(AssertionError, match="No calls recorded"):
        # Act
        handler.call_log.last  # noqa: B018


async def test_assert_called_with_json_none_fails_when_json_present(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    handler = some_http_service_mock.expect_request("/jn1", method="POST")
    handler.respond_with_json({})

    # Act
    await client.post(some_http_service_mock.url_for("/jn1"), json={"k": "v"})

    # Assert
    with pytest.raises(AssertionError, match="Expected json"):
        handler.call_log.assert_called_with(json=None)


async def test_assert_called_with_json_none_passes_when_no_json_body(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    handler = some_http_service_mock.expect_request("/jn2", method="GET")
    handler.respond_with_json({})

    # Act
    await client.get(some_http_service_mock.url_for("/jn2"))

    # Assert
    handler.call_log.assert_called_with(json=None)


async def test_assert_called_with_omitting_json_skips_check(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    handler = some_http_service_mock.expect_request("/jn3", method="POST")
    handler.respond_with_json({})

    # Act
    await client.post(some_http_service_mock.url_for("/jn3"), json={"x": 1})

    # Assert
    handler.call_log.assert_called_with()


async def test_assert_called_with_data_bytes_passes(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    handler = some_http_service_mock.expect_request("/db1", method="POST")
    handler.respond_with_json({})

    # Act
    await client.post(
        some_http_service_mock.url_for("/db1"),
        data=b"\xca\xfe",
        headers={"Content-Type": "application/octet-stream"},
    )

    # Assert
    handler.call_log.assert_called_with(data=b"\xca\xfe")


async def test_assert_called_with_data_bytes_fails_on_mismatch(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    handler = some_http_service_mock.expect_request("/db2", method="POST")
    handler.respond_with_json({})

    # Act
    await client.post(
        some_http_service_mock.url_for("/db2"),
        data=b"\x01\x02",
        headers={"Content-Type": "application/octet-stream"},
    )

    # Assert
    with pytest.raises(AssertionError, match="Expected data"):
        handler.call_log.assert_called_with(data=b"\xff\xfe")


async def test_assert_called_with_data_matches_text_plain_body(
    client, some_http_service_mock: HTTPServerMock
):
    """
    data= in assert_called_with must work for text/plain bodies (stored in
    call.text, not call.data).
    """
    # Arrange
    handler = some_http_service_mock.expect_request("/tp1", method="POST")
    handler.respond_with_json({})

    # Act
    await client.post(
        some_http_service_mock.url_for("/tp1"),
        data="hello",
        headers={"Content-Type": "text/plain"},
    )

    # Assert
    handler.call_log.assert_called_with(data=b"hello")


async def test_assert_called_with_data_fails_on_wrong_text_plain_body(
    client, some_http_service_mock: HTTPServerMock
):
    # Arrange
    handler = some_http_service_mock.expect_request("/tp2", method="POST")
    handler.respond_with_json({})

    # Act
    await client.post(
        some_http_service_mock.url_for("/tp2"),
        data="actual",
        headers={"Content-Type": "text/plain"},
    )

    # Assert
    with pytest.raises(AssertionError, match="Expected data"):
        handler.call_log.assert_called_with(data=b"wrong")


async def test_assert_called_with_data_none_on_empty_body(
    client, some_http_service_mock: HTTPServerMock
):
    """data=None passes when the request had no body."""
    # Arrange
    handler = some_http_service_mock.expect_request("/nobody", method="GET")
    handler.respond_with_json({})

    # Act
    await client.get(some_http_service_mock.url_for("/nobody"))

    # Assert
    handler.call_log.assert_called_with(data=None)


async def test_assert_called_with_text_passes(
    client, some_http_service_mock: HTTPServerMock
):
    """assert_called_with(text=) must succeed when text matches."""
    # Arrange
    handler = some_http_service_mock.expect_request("/txt2", method="POST")
    handler.respond_with_json({})

    # Act
    await client.post(
        some_http_service_mock.url_for("/txt2"),
        data="match me",
        headers={"Content-Type": "text/plain"},
    )

    # Assert
    handler.call_log.assert_called_with(text="match me")


async def test_assert_called_with_data_none_passes_for_json_body(
    client, some_http_service_mock: HTTPServerMock
):
    """
    data=None passes even when the request body was JSON, because JSON
    is stored in call.json, not call.data.  This is by design — data=None
    means "no raw binary body", which is true for JSON-parsed bodies too.
    """
    # Arrange
    handler = some_http_service_mock.expect_request("/jdn", method="POST")
    handler.respond_with_json({})

    # Act
    await client.post(some_http_service_mock.url_for("/jdn"), json={"k": "v"})

    # Assert
    handler.call_log.assert_called_with(data=None)


async def test_assert_called_with_out_of_range_negative_index(
    client, some_http_service_mock: HTTPServerMock
):
    """Negative call_index that is out of range must raise AssertionError."""
    # Arrange
    handler = some_http_service_mock.expect_request("/neg", method="GET")
    handler.respond_with_json({})

    # Act
    await client.get(some_http_service_mock.url_for("/neg"))

    # Assert — only 1 call, index -5 is out of range
    with pytest.raises(AssertionError, match="out of range"):
        handler.call_log.assert_called_with(call_index=-5)
