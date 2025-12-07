from typing import Callable

import pytest_asyncio
from aiohttp import web

from .web_service_mock import MockData, WebServiceMock


@pytest_asyncio.fixture
async def external_service_mock(aiohttp_server):
    """
    Mock server for an external service

    Returns:
    function for adding an API to the server
    """

    async def _create_mock() -> tuple[
        str, Callable[[MockData], list[dict[str, any]]]
    ]:
        app = web.Application()
        web_service = WebServiceMock()
        # The route catches requests for any path with any method.
        # The web_service is responsible for actual routing, allowing new
        # APIs to be added at server runtime.
        app.router.add_route("*", "/{tail:.+}", web_service.handle)
        server = await aiohttp_server(app)
        return f"http://{server.host}:{server.port}", web_service.add_mock_data

    return _create_mock
