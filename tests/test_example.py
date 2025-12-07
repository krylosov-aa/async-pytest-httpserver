import pytest
from http import HTTPStatus

from aiohttp.web import json_response
from . import settings


@pytest.mark.asyncio
async def test_example(client, some_service_mock_api):
    # Arrange
    calls_info = some_service_mock_api(
        json_response(
            {"result": "some_result"},
            status=HTTPStatus.OK,
        )
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
