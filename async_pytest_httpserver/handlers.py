from __future__ import annotations

import asyncio
import os
from collections.abc import Awaitable, Callable
from copy import deepcopy
from enum import Enum
from http import HTTPStatus
from inspect import isawaitable
from typing import Any, cast, overload

from aiohttp import web

from .call_info import CallLog

ResponseHandler = Callable[
    [web.Request], web.Response | Awaitable[web.Response]
]

PostHook = Callable[
    [web.Request, web.Response],
    web.Response | Awaitable[web.Response],
]


class HandlerType(Enum):
    """Lifetime mode of a registered handler."""

    PERMANENT = "permanent"
    ONESHOT = "oneshot"
    ORDERED = "ordered"


class Delay:
    """Post-hook that pauses response delivery to simulate slow servers."""

    @overload
    def __init__(self, *, sec: float) -> None:
        """"""

    @overload
    def __init__(self, *, ms: int) -> None:
        """"""

    def __init__(
        self,
        *,
        sec: float | None = None,
        ms: int | None = None,
    ) -> None:
        if sec is None and ms is None:
            raise TypeError("Specify the delay in seconds or milliseconds.")
        if sec is not None and ms is not None:
            raise TypeError(
                "You can't specify a delay in both seconds and milliseconds."
            )
        self._seconds = cast("float", sec) if ms is None else ms / 1000

    async def __call__(
        self, request: web.Request, response: web.Response
    ) -> web.Response:
        await asyncio.sleep(self._seconds)
        return response


class Garbage:
    """
    Post-hook that corrupts the response body with random bytes.
    Prepends and/or appends random bytes to the response body.
    """

    def __init__(self, prefix_size: int = 0, suffix_size: int = 0) -> None:
        self._prefix_size = prefix_size
        self._suffix_size = suffix_size

    async def __call__(
        self, request: web.Request, response: web.Response
    ) -> web.Response:
        prefix = os.urandom(self._prefix_size)
        suffix = os.urandom(self._suffix_size)
        raw = response.body
        original = raw if isinstance(raw, bytes) else b""
        return web.Response(
            status=response.status,
            headers=self._non_content_type_headers(response),
            body=prefix + original + suffix,
            content_type=response.content_type,
        )

    @staticmethod
    def _non_content_type_headers(
        response: web.Response,
    ) -> dict[str, str]:
        return {
            k: v
            for k, v in response.headers.items()
            if k.upper() != "CONTENT-TYPE"
        }


class Chain:
    """
    Post-hook that composes multiple hooks and applies them sequentially.
    Each hook receives the response produced by the previous one, so hooks
    are applied in registration order.
    """

    def __init__(self, *hooks: PostHook) -> None:
        self._hooks = hooks

    async def __call__(
        self, request: web.Request, response: web.Response
    ) -> web.Response:
        for hook in self._hooks:
            result = hook(request, response)
            if isawaitable(result):
                response = await result
            else:
                response = result
        return response


_NO_RESPONSE_MSG = (
    "[async-pytest-httpserver] No response configured for handler"
)

_SequenceItem = web.Response | tuple[int, Any] | ResponseHandler


class RequestHandler:
    """
    Configures the response for a single registered handler.
    """

    def __init__(self, handler_type: HandlerType) -> None:
        self.handler_type = handler_type
        self.call_log: CallLog = CallLog()
        self._response: web.Response | ResponseHandler | None = None
        self._post_hooks: list[PostHook] = []
        self._sequence: list[_SequenceItem] = []
        self._sequence_idx: int = 0

    def respond_with_json(
        self,
        data: Any,
        *,
        status: int = HTTPStatus.OK,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Respond with a JSON body."""
        self._response = web.json_response(
            data, status=status, headers=headers
        )

    def respond_with_data(
        self,
        text: str = "",
        *,
        status: int = HTTPStatus.OK,
        content_type: str = "text/plain",
        headers: dict[str, str] | None = None,
    ) -> None:
        """Respond with a plain-text or custom-format body."""
        self._response = web.Response(
            text=text,
            status=status,
            content_type=content_type,
            headers=headers,
        )

    def respond_with_response(self, response: web.Response) -> None:
        """
        Respond with a pre-built ``web.Response``.

        The object is deep-copied on each request so it can be reused.
        """
        self._response = response

    def respond_with_handler(self, handler: ResponseHandler) -> None:
        """Respond using a callable that builds the response dynamically."""
        self._response = handler

    def respond_with_sequence(self, responses: list[_SequenceItem]) -> None:
        """
        Configure a sequence of responses served in order.

        The last item repeats for all calls past the end.
        """
        if not responses:
            raise ValueError(
                "Sequence must not be empty — provide at least one response."
            )
        self._sequence = list(responses)
        self._sequence_idx = 0

    def with_post_hook(self, hook: PostHook) -> RequestHandler:
        """Attach a post-hook."""
        self._post_hooks.append(hook)
        return self

    async def build_response(self, request: web.Request) -> web.Response:
        if self._sequence:
            response = await self._get_from_sequence(request)
        elif self._response is None:
            return web.Response(
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
                text=_NO_RESPONSE_MSG,
            )
        else:
            response = await self._invoke_response(request)
        return await self._apply_hooks(request, response)

    async def _get_from_sequence(self, request: web.Request) -> web.Response:
        idx = min(self._sequence_idx, len(self._sequence) - 1)
        item = self._sequence[idx]
        if self._sequence_idx < len(self._sequence) - 1:
            self._sequence_idx += 1
        return await self._invoke_item(request, item)

    async def _invoke_response(self, request: web.Request) -> web.Response:
        if isinstance(self._response, web.Response):
            return deepcopy(self._response)
        result = self._response(request)  # type: ignore[misc]
        if isawaitable(result):
            return await result
        return result

    async def _apply_hooks(
        self, request: web.Request, response: web.Response
    ) -> web.Response:
        for hook in self._post_hooks:
            result = hook(request, response)
            if isawaitable(result):
                response = await result
            else:
                response = result
        return response

    @staticmethod
    async def _invoke_item(
        request: web.Request, item: _SequenceItem
    ) -> web.Response:
        if isinstance(item, web.Response):
            return deepcopy(item)
        if isinstance(item, tuple):
            status_code, json_data = item[0], item[1]
            return web.json_response(json_data, status=status_code)
        result = item(request)
        if isawaitable(result):
            return await result
        return result
