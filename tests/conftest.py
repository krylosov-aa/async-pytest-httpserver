from typing import Any, AsyncGenerator, Awaitable, Callable

import pytest
import pytest_asyncio
from aiohttp import web, ClientSession

from async_pytest_httpserver import MockData
from . import settings


@pytest_asyncio.fixture
async def some_service_mock(
    external_service_mock,
) -> AsyncGenerator[Callable[[MockData], list[dict[str, any]]]]:
    """
    Example of how to use
    """
    url, add_mock_data = await external_service_mock()
    # You have a URL for an external service specified somewhere.
    # We're replacing it with a new one as part of our testing.
    old_url = settings.EXTERNAL_SERVICE_URL
    settings.EXTERNAL_SERVICE_URL = url
    yield add_mock_data
    settings.EXTERNAL_SERVICE_URL = old_url


@pytest.fixture
def some_service_mock_api(some_service_mock):
    """An example of a fixture where a specific API is mocked"""

    def _create_mock(
        response: web.Response
        | Callable[[web.Request], web.Response | Awaitable[web.Response]],
    ) -> list[dict[str, Any]]:
        return some_service_mock(MockData("POST", "/some_api", response))

    return _create_mock


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[ClientSession, Any]:
    async with ClientSession() as session:
        yield session
