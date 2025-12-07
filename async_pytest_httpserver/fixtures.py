from typing import Any, Awaitable, Callable, List, Tuple
from aiohttp import web
from aiohttp.test_utils import TestServer
import pytest_asyncio

from .web_service_mock import MockData, WebServiceMock

AddMockDataFunc = Callable[[MockData], List[dict[str, Any]]]


@pytest_asyncio.fixture
async def external_service_mock(
    aiohttp_server: Callable[[web.Application], Awaitable[TestServer]],
) -> Callable[[], Awaitable[Tuple[str, AddMockDataFunc]]]:
    """Mock server for an external service."""

    async def _create_mock() -> Tuple[str, AddMockDataFunc]:
        app = web.Application()
        web_service = WebServiceMock()

        app.router.add_route("*", "/{tail:.+}", web_service.handle)

        server = await aiohttp_server(app)
        return str(server.make_url("")), web_service.add_mock_data

    return _create_mock
