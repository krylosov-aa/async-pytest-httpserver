from copy import deepcopy
from dataclasses import dataclass
from inspect import isawaitable
from typing import Any, Awaitable, Callable

from aiohttp import web


ResponseHandler = Callable[
    [web.Request], web.Response | Awaitable[web.Response]
]


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
        self._call_info: dict[str, dict[str, list[dict[str, Any]]]] = {}

    async def handle(self, request: web.Request) -> web.Response:
        """
        The method searches for a mock among the registered MockData,
        stores the request information, and returns a mock response.
        """
        for mock in self._mock_data:
            if (
                mock.method.lower() == request.method.lower()
                and mock.path == request.path
            ):
                await self._save_request(mock.method, mock.path, request)
                if isinstance(mock.response, web.Response):
                    return deepcopy(mock.response)

                response = mock.response(request)
                if isawaitable(response):
                    return await response
                return response

        raise LookupError(
            f"Mock with method={request.method} "
            f"and url={request.path} not found"
        )

    def add_mock_data(self, mock_data: MockData) -> list[dict[str, Any]]:
        """Saves a new mock and returns a reference to the call history"""
        self._mock_data.append(mock_data)

        url_data = self._call_info.get(mock_data.path) or {}
        method_data = url_data.get(mock_data.method) or []
        url_data[mock_data.method] = method_data
        self._call_info[mock_data.path] = url_data
        return self._call_info[mock_data.path][mock_data.method]

    async def _save_request(
        self, method: str, path: str, request: web.Request
    ) -> None:
        data: dict[str, Any] = {"headers": request.headers}

        if request.can_read_body:
            if request.content_type == "application/json":
                data["json"] = await request.json()
            elif request.content_type == "text/plain":
                data["text"] = await request.text()

        self._call_info[path][method].append(data)
