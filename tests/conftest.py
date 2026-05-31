from collections.abc import AsyncGenerator, Awaitable, Callable
from typing import Any

import pytest
import pytest_asyncio
from aiohttp import ClientSession, web

from async_pytest_httpserver import (
    AddMockDataFunc,
    MockData,
    ResponseHandler,
)

from . import settings

_ExternalMock = Callable[[], Awaitable[tuple[str, AddMockDataFunc]]]
_MockApiFactory = Callable[
    [web.Response | ResponseHandler], list[dict[str, Any]]
]


@pytest_asyncio.fixture
async def some_service_mock(
    external_service_mock: _ExternalMock,
) -> AsyncGenerator[AddMockDataFunc, None]:
    """
    Example of how to use
    """
    url, add_mock_data = await external_service_mock()
    old_url = settings.EXTERNAL_SERVICE_URL
    settings.EXTERNAL_SERVICE_URL = url
    try:
        yield add_mock_data
    finally:
        settings.EXTERNAL_SERVICE_URL = old_url


@pytest.fixture
def some_service_mock_api(
    some_service_mock: AddMockDataFunc,
) -> _MockApiFactory:
    """An example of a fixture where a specific API is mocked"""

    def _create_mock(
        response: web.Response | ResponseHandler,
    ) -> list[dict[str, Any]]:
        return some_service_mock(MockData("POST", "/some_api", response))

    return _create_mock


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[ClientSession, None]:
    async with ClientSession() as session:
        yield session
