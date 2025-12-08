from typing import Any, AsyncGenerator, Awaitable, Callable, List

import pytest
import pytest_asyncio
from aiohttp import web, ClientSession

from async_pytest_httpserver import (
    MockData,
    AddMockDataFunc,
    ResponseHandler,
)
from . import settings


@pytest_asyncio.fixture
async def some_service_mock(
    external_service_mock: Callable[
        [], Awaitable[tuple[str, AddMockDataFunc]]
    ],
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
) -> Callable[
    [web.Response | ResponseHandler],
    List[dict[str, Any]],
]:
    """An example of a fixture where a specific API is mocked"""

    def _create_mock(
        response: web.Response | ResponseHandler,
    ) -> List[dict[str, Any]]:
        return some_service_mock(MockData("POST", "/some_api", response))

    return _create_mock


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[ClientSession, None]:
    async with ClientSession() as session:
        yield session
