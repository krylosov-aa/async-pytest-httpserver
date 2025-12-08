import pytest
from http import HTTPStatus
from async_pytest_httpserver import (
    MockData,
)
from aiohttp.web import json_response, Request, Response
from . import settings


@pytest.mark.asyncio
async def test_static_mock(client, some_service_mock):
    # Arrange
    response = json_response(
        {"result": "some_result"},
        status=HTTPStatus.OK,
    )
    calls_info = some_service_mock(MockData("POST", "/some_api", response))

    # Act
    response = await client.post(
        f"{settings.EXTERNAL_SERVICE_URL}/some_api",
        json={"text": "text"},
    )

    # Assert
    assert response.ok
    data = await response.json()
    assert data["result"] == "some_result"

    assert len(calls_info) == 1
    call_info = calls_info[0]
    assert call_info["json"] == {"text": "text"}


async def async_mock_handler(request: Request) -> Response:
    return json_response(
        {"result": "some_result"},
        status=HTTPStatus.OK,
    )


@pytest.mark.asyncio
async def test_async_handler(client, some_service_mock):
    # Arrange
    calls_info = some_service_mock(
        MockData("POST", "/some_api", async_mock_handler)
    )

    # Act
    response = await client.post(
        f"{settings.EXTERNAL_SERVICE_URL}/some_api",
        json={"text": "text"},
    )

    # Assert
    assert response.ok
    data = await response.json()
    assert data["result"] == "some_result"

    assert len(calls_info) == 1
    call_info = calls_info[0]
    assert call_info["json"] == {"text": "text"}


def sync_mock_handler(request: Request) -> Response:
    return json_response(
        {"result": "some_result"},
        status=HTTPStatus.OK,
    )


@pytest.mark.asyncio
async def test_sync_handler(client, some_service_mock):
    # Arrange
    calls_info = some_service_mock(
        MockData("POST", "/some_api", sync_mock_handler)
    )

    # Act
    response = await client.post(
        f"{settings.EXTERNAL_SERVICE_URL}/some_api",
        json={"text": "text"},
    )

    # Assert
    assert response.ok
    data = await response.json()
    assert data["result"] == "some_result"

    assert len(calls_info) == 1
    call_info = calls_info[0]
    assert call_info["json"] == {"text": "text"}
