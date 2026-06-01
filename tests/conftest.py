from __future__ import annotations

from collections.abc import AsyncGenerator, Awaitable, Callable

import pytest
import pytest_asyncio
from aiohttp import ClientSession

from async_pytest_httpserver import HTTPServerMock

from . import settings

_MockFactory = Callable[[], Awaitable[HTTPServerMock]]


@pytest_asyncio.fixture
async def some_http_service_mock(
    http_server: _MockFactory, monkeypatch: pytest.MonkeyPatch
) -> AsyncGenerator[HTTPServerMock, None]:
    mock = await http_server()
    monkeypatch.setattr(settings, "EXTERNAL_SERVICE_URL", mock.base_url)
    yield mock


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[ClientSession, None]:
    async with ClientSession() as session:
        yield session
