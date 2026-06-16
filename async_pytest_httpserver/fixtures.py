from __future__ import annotations

from collections.abc import Awaitable, Callable
from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest_asyncio
from aiohttp import web

if TYPE_CHECKING:
    from aiohttp.test_utils import TestServer

from .conflict_policy import ConflictPolicy
from .http_server_mock import HTTPServerMock

_MockFactory = Callable[..., Awaitable[HTTPServerMock]]


@pytest_asyncio.fixture
async def http_server(
    aiohttp_server: Callable[[web.Application], Awaitable[TestServer]],
) -> _MockFactory:
    """
    Factory fixture that creates isolated mock HTTP servers.
    Call it once per external service you need to mock.

    Usage::

        @pytest_asyncio.fixture
        async def payment_mock(http_server, monkeypatch):
            mock = await http_server()
            monkeypatch.setattr(settings, "PAYMENT_URL", mock.base_url)
            yield mock
    """

    async def _create(
        no_handler_status_code: int = HTTPStatus.NOT_FOUND,
        conflict_policy: ConflictPolicy = ConflictPolicy.LAST_WINS,
    ) -> HTTPServerMock:
        app = web.Application()
        mock = HTTPServerMock(
            no_handler_status_code=no_handler_status_code,
            conflict_policy=conflict_policy,
        )
        app.router.add_route("*", "/", mock.handle)
        app.router.add_route("*", "/{tail:.+}", mock.handle)
        server = await aiohttp_server(app)
        mock.base_url = str(server.make_url(""))
        return mock

    return _create
