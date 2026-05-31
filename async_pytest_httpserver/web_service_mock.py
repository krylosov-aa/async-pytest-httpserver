from collections.abc import Awaitable, Callable
from copy import deepcopy
from dataclasses import dataclass
from http import HTTPStatus
from inspect import isawaitable
from typing import Any

from aiohttp import web

ResponseHandler = Callable[
    [web.Request], web.Response | Awaitable[web.Response]
]

_RequestLog = dict[str, Any]
_MethodCalls = list[_RequestLog]


@dataclass
class MockData:
    method: str  # the method we replace
    path: str  # the API path we are replacing
    response: web.Response | ResponseHandler


class WebServiceMock:
    """
    A mock web service with a single API handle.
        Intended use:
        1. Start aiohttp_server with a universal route to the handle
        2. Add real APIs via add_mock_data
    """

    def __init__(self) -> None:
        self._mock_data: list[MockData] = []
        self._call_info: dict[str, dict[str, _MethodCalls]] = {}

    async def handle(self, request: web.Request) -> web.Response:
        """
        The method searches for a mock among the registered MockData,
        stores the request information, and returns a mock response.
        """
        mock = self._find_mock(request)
        if mock is None:
            return web.Response(
                status=HTTPStatus.NOT_FOUND,
                text=(
                    f"[async-pytest-httpserver] No mock registered for "
                    f"{request.method} {request.path}"
                ),
            )
        await self._save_request(mock.method, mock.path, request)
        if isinstance(mock.response, web.Response):
            return deepcopy(mock.response)
        response = mock.response(request)
        if isawaitable(response):
            return await response
        return response

    def add_mock_data(self, mock_data: MockData) -> list[dict[str, Any]]:
        """Saves a new mock and returns a reference to the call history"""
        self._mock_data.append(mock_data)

        url_data = self._call_info.get(mock_data.path) or {}
        method_data = url_data.get(mock_data.method) or []
        url_data[mock_data.method] = method_data
        self._call_info[mock_data.path] = url_data
        return self._call_info[mock_data.path][mock_data.method]

    def _find_mock(self, request: web.Request) -> "MockData | None":
        for mock in self._mock_data:
            method_match = mock.method.lower() == request.method.lower()
            if method_match and mock.path == request.path:
                return mock
        return None

    async def _save_request(
        self, method: str, path: str, request: web.Request
    ) -> None:
        data: _RequestLog = {"headers": request.headers}

        if request.can_read_body:
            if request.content_type == "application/json":
                data["json"] = await request.json()
            elif request.content_type == "text/plain":
                data["text"] = await request.text()

        self._call_info[path][method].append(data)
