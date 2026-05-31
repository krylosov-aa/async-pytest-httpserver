from collections.abc import Awaitable, Callable
from typing import Any

import pytest_asyncio
from aiohttp import web
from aiohttp.test_utils import TestServer

from .web_service_mock import MockData, WebServiceMock

AddMockDataFunc = Callable[[MockData], list[dict[str, Any]]]
_MockCreator = Callable[[], Awaitable[tuple[str, AddMockDataFunc]]]


@pytest_asyncio.fixture
async def external_service_mock(
    aiohttp_server: Callable[[web.Application], Awaitable[TestServer]],
) -> _MockCreator:
    """Mock server for an external service."""

    async def _create_mock() -> tuple[str, AddMockDataFunc]:
        app = web.Application()
        web_service = WebServiceMock()

        app.router.add_route("*", "/{tail:.+}", web_service.handle)

        server = await aiohttp_server(app)
        return str(server.make_url("")), web_service.add_mock_data

    return _create_mock
