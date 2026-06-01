from collections.abc import AsyncGenerator, Awaitable, Callable

import pytest
import pytest_asyncio
from aiohttp import ClientSession
from async_pytest_httpserver import HTTPServerMock

from app.clients import NotificationClient, WeatherClient

_MockFactory = Callable[[], Awaitable[HTTPServerMock]]


@pytest_asyncio.fixture
async def mock(http_server: _MockFactory) -> HTTPServerMock:
    """A bare mock server for feature-focused tests."""
    return await http_server()


@pytest_asyncio.fixture
async def weather_mock(http_server: _MockFactory) -> HTTPServerMock:
    return await http_server()


@pytest_asyncio.fixture
async def notify_mock(http_server: _MockFactory) -> HTTPServerMock:
    return await http_server()


@pytest.fixture
def weather_client(weather_mock: HTTPServerMock) -> WeatherClient:
    return WeatherClient(base_url=weather_mock.base_url)


@pytest.fixture
def notify_client(notify_mock: HTTPServerMock) -> NotificationClient:
    return NotificationClient(base_url=notify_mock.base_url)


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[ClientSession, None]:
    async with ClientSession() as session:
        yield session
