from __future__ import annotations

import json as json_module
from collections import deque
from http import HTTPStatus
from typing import TYPE_CHECKING, Any

from aiohttp import web
from multidict import CIMultiDictProxy, MultiDictProxy

from .call_info import CallInfo
from .conflict_policy import ConflictError, ConflictPolicy
from .handlers import HandlerType, RequestHandler
from .matchers import (
    UNDEFINED,
    HeaderValueMatcher,
    RequestMatcher,
    _BaseMatcher,
    _PathArg,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

_HandlerEntry = tuple[_BaseMatcher, RequestHandler]
_PREFIX = "[async-pytest-httpserver]"
_ERROR_RESPONSE_MSG = f"{_PREFIX} Handler raised an exception"
_DEFAULT_METHOD = "GET"

_ExpectArg = _PathArg | _BaseMatcher | None


class HTTPServerMock:
    """Async mock HTTP server."""

    def __init__(
        self,
        *,
        no_handler_status_code: int = HTTPStatus.NOT_FOUND,
        conflict_policy: ConflictPolicy = ConflictPolicy.LAST_WINS,
    ) -> None:
        self.base_url: str = ""
        self._no_handler_status_code = no_handler_status_code
        self._conflict_policy = conflict_policy
        self._last_wins = conflict_policy != ConflictPolicy.FIRST_WINS
        self._permanent: list[_HandlerEntry] = []
        self._oneshot: list[_HandlerEntry] = []
        self._ordered: deque[_HandlerEntry] = deque()
        self._log: list[tuple[CallInfo, web.Response]] = []
        self._handler_errors: list[Exception] = []
        self._unmatched_log: list[CallInfo] = []

    @property
    def no_handler_status_code(self) -> int:
        """HTTP status code returned when no registered handler matches."""
        return self._no_handler_status_code

    def expect_request(
        self,
        path: _ExpectArg = None,
        method: str | list[str] = _DEFAULT_METHOD,
        *,
        query_string: str | dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        json: Any = UNDEFINED,
        json_contains: Any = UNDEFINED,
        data: str | bytes | None = None,
        header_value_matcher: HeaderValueMatcher | None = None,
    ) -> RequestHandler:
        """
        Register a permanent handler that responds to every matching request.
        """
        return self._register(
            HandlerType.PERMANENT,
            path,
            method,
            query_string=query_string,
            headers=headers,
            json=json,
            json_contains=json_contains,
            data=data,
            header_value_matcher=header_value_matcher,
        )

    def expect_oneshot_request(
        self,
        path: _ExpectArg = None,
        method: str | list[str] = _DEFAULT_METHOD,
        *,
        query_string: str | dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        json: Any = UNDEFINED,
        json_contains: Any = UNDEFINED,
        data: str | bytes | None = None,
        header_value_matcher: HeaderValueMatcher | None = None,
    ) -> RequestHandler:
        """
        Register a handler that responds exactly once, then removes itself.

        Call ``mock.check()`` at the end of the test to verify it was consumed.
        """
        return self._register(
            HandlerType.ONESHOT,
            path,
            method,
            query_string=query_string,
            headers=headers,
            json=json,
            json_contains=json_contains,
            data=data,
            header_value_matcher=header_value_matcher,
        )

    def expect_ordered_request(
        self,
        path: _ExpectArg = None,
        method: str | list[str] = _DEFAULT_METHOD,
        *,
        query_string: str | dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        json: Any = UNDEFINED,
        json_contains: Any = UNDEFINED,
        data: str | bytes | None = None,
        header_value_matcher: HeaderValueMatcher | None = None,
    ) -> RequestHandler:
        """
        Register a handler that must be called in registration order.

        Takes priority over all other handlers. A mismatch returns 500.
        Call ``mock.check()`` at the end to assert all were consumed.
        """
        return self._register(
            HandlerType.ORDERED,
            path,
            method,
            query_string=query_string,
            headers=headers,
            json=json,
            json_contains=json_contains,
            data=data,
            header_value_matcher=header_value_matcher,
        )

    def bake(self, **defaults: Any) -> BakedMock:
        """Return a ``BakedMock`` with pre-filled defaults"""
        return BakedMock(self, defaults)

    def url_for(self, path: str) -> str:
        """Build a full URL for the given path."""
        base = self.base_url.rstrip("/")
        return f"{base}/{path.lstrip('/')}"

    @property
    def missed_requests(self) -> list[CallInfo]:
        """Requests that matched no handler (including ordered mismatches)."""
        return list(self._unmatched_log)

    @property
    def log(self) -> list[tuple[CallInfo, web.Response]]:
        """
        All ``(CallInfo, Response)`` pairs since last ``clear()``.
        Unmatched requests are excluded.
        """
        return list(self._log)

    def assert_request_made(
        self, matcher: _BaseMatcher, *, count: int = 1
    ) -> None:
        """Assert exactly ``count`` recorded requests match ``matcher``."""
        actual = sum(
            1 for call, _ in self._log if matcher.matches_call_info(call)
        )
        if actual != count:
            raise AssertionError(
                f"Expected {count} request(s) matching {matcher!r}, "
                f"got {actual}"
            )

    def iter_matching_requests(
        self, matcher: _BaseMatcher
    ) -> list[tuple[CallInfo, web.Response]]:
        """Return logged pairs matching ``matcher``."""
        return [
            pair for pair in self._log if matcher.matches_call_info(pair[0])
        ]

    def check_handler_errors(self) -> None:
        """Re-raise the first exception caught in a handler, if any."""
        if self._handler_errors:
            raise self._handler_errors[0]

    def check(self, *, all_called: bool = False) -> None:
        """
        Assert no handler errors and all oneshot/ordered handlers consumed.

        Pass ``all_called=True`` to also assert every permanent handler was
            called at least once.
        """
        self.check_handler_errors()
        if all_called:
            self._check_all_permanent_called()
        uncalled = [*self._oneshot, *self._ordered]
        if uncalled:
            descriptions = "\n".join(
                f"  - {matcher!r}" for matcher, _ in uncalled
            )
            raise AssertionError(
                f"{_PREFIX} {len(uncalled)} handler(s) were never called:"
                f"\n{descriptions}"
            )

    def clear(self) -> None:
        """Remove all handlers and reset call history. Server keeps running."""
        self._permanent.clear()
        self._oneshot.clear()
        self._ordered.clear()
        self._log.clear()
        self._handler_errors.clear()
        self._unmatched_log.clear()

    def format_matchers(self) -> str:
        """Summary of registered handlers with call counts."""
        lines = ["Registered handlers:"]
        pools = [
            ("PERMANENT", self._permanent),
            ("ONESHOT", self._oneshot),
            ("ORDERED", self._ordered),
        ]
        for label, pool in pools:
            self._format_pool(lines, label, pool)
        return "\n".join(lines)

    async def handle(self, request: web.Request) -> web.Response:
        """aiohttp wildcard route — not intended to be called directly."""
        body = await request.read()

        handler = self._match_ordered(request, body)
        if handler is not None:
            return await self._dispatch(request, body, handler)

        if self._ordered:
            await self._log_unmatched(request, body)
            return self._ordered_mismatch(request)

        handler = self._match_pool(
            self._oneshot,
            request,
            body,
            remove=True,
            last_wins=self._last_wins,
        )
        if handler is not None:
            return await self._dispatch(request, body, handler)

        handler = self._match_pool(
            self._permanent,
            request,
            body,
            remove=False,
            last_wins=self._last_wins,
        )
        if handler is not None:
            return await self._dispatch(request, body, handler)

        await self._log_unmatched(request, body)
        return web.Response(
            status=self._no_handler_status_code,
            text=(
                f"{_PREFIX} No mock registered for "
                f"{request.method} {request.path}"
            ),
        )

    def _check_all_permanent_called(self) -> None:
        uncalled = sum(
            1 for _, handler in self._permanent if len(handler.call_log) == 0
        )
        if uncalled:
            raise AssertionError(
                f"{_PREFIX} {uncalled} permanent handler(s) were never called"
            )

    def _register(
        self,
        kind: HandlerType,
        path: _ExpectArg,
        method: str | list[str],
        *,
        query_string: str | dict[str, str] | None,
        headers: dict[str, str] | None,
        json: Any,
        json_contains: Any,
        data: str | bytes | None,
        header_value_matcher: HeaderValueMatcher | None,
    ) -> RequestHandler:
        matcher = self._build_matcher(
            path,
            method,
            query_string=query_string,
            headers=headers,
            json=json,
            json_contains=json_contains,
            data=data,
            header_value_matcher=header_value_matcher,
        )
        if self._conflict_policy == ConflictPolicy.ERROR:
            self._check_conflict(matcher, kind)
        handler = RequestHandler(kind)
        if kind == HandlerType.PERMANENT:
            self._permanent.append((matcher, handler))
        elif kind == HandlerType.ONESHOT:
            self._oneshot.append((matcher, handler))
        else:
            self._ordered.append((matcher, handler))
        return handler

    def _check_conflict(
        self, matcher: _BaseMatcher, kind: HandlerType
    ) -> None:
        pool = self._pool_for_conflict(kind)
        for existing, _ in pool:
            if existing.could_overlap(matcher):
                raise ConflictError(
                    f"{_PREFIX} Handler conflict: "
                    f"{matcher!r} overlaps with {existing!r}"
                )

    def _pool_for_conflict(self, kind: HandlerType) -> list[_HandlerEntry]:
        if kind == HandlerType.PERMANENT:
            return list(self._permanent)
        if kind == HandlerType.ONESHOT:
            return list(self._oneshot)
        return list(self._ordered)

    def _match_ordered(
        self, request: web.Request, body: bytes
    ) -> RequestHandler | None:
        if not self._ordered:
            return None
        matcher, handler = self._ordered[0]
        if matcher.matches(request, body):
            self._ordered.popleft()
            return handler
        return None

    def _ordered_mismatch(self, request: web.Request) -> web.Response:
        expected_matcher, _ = self._ordered[0]
        return web.Response(
            status=HTTPStatus.INTERNAL_SERVER_ERROR,
            text=(
                f"{_PREFIX} Ordered handler expected "
                f"{expected_matcher!r}, got "
                f"{request.method} {request.path}"
            ),
        )

    async def _log_unmatched(self, request: web.Request, body: bytes) -> None:
        call_info = await self._build_call_info(request, body)
        self._unmatched_log.append(call_info)

    async def _dispatch(
        self,
        request: web.Request,
        body: bytes,
        handler: RequestHandler,
    ) -> web.Response:
        call_info = await self._build_call_info(request, body)
        handler.call_log._append(call_info)
        try:
            response = await handler.build_response(request)
        except Exception as exc:
            self._handler_errors.append(exc)
            response = web.Response(
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
                text=_ERROR_RESPONSE_MSG,
            )
        self._log.append((call_info, response))
        return response

    async def _build_call_info(
        self, request: web.Request, body: bytes
    ) -> CallInfo:
        parsed_json, parsed_text, raw = self._parse_body(
            body, request.content_type
        )
        return CallInfo(
            method=request.method,
            path=request.path,
            headers=CIMultiDictProxy(request.headers),
            query=MultiDictProxy(request.rel_url.query),
            json=parsed_json,
            text=parsed_text,
            data=raw,
        )

    def _parse_body(
        self, body: bytes, content_type: str
    ) -> tuple[Any | None, str | None, bytes | None]:
        if not body:
            return None, None, None
        if content_type == "application/json":
            return self._parse_json(body)
        if content_type == "text/plain":
            return None, body.decode("utf-8", errors="replace"), None
        return None, None, body

    @staticmethod
    def _match_pool(
        pool: list[_HandlerEntry],
        request: web.Request,
        body: bytes,
        *,
        remove: bool,
        last_wins: bool,
    ) -> RequestHandler | None:
        items = list(enumerate(pool))
        if last_wins:
            items = list(reversed(items))
        for idx, (matcher, handler) in items:
            if matcher.matches(request, body):
                if remove:
                    pool.pop(idx)
                return handler
        return None

    @staticmethod
    def _format_pool(
        lines: list[str], label: str, pool: Iterable[_HandlerEntry]
    ) -> None:
        for matcher, handler in pool:
            calls = len(handler.call_log)
            lines.append(f"  [{label}] {matcher!r} — {calls} call(s)")

    @staticmethod
    def _has_extra_matcher_params(
        method: str | list[str],
        query_string: str | dict[str, str] | None,
        headers: dict[str, str] | None,
        json: Any,
        json_contains: Any,
        data: str | bytes | None,
        header_value_matcher: HeaderValueMatcher | None,
    ) -> bool:
        if method != _DEFAULT_METHOD:
            return True
        if query_string is not None or headers is not None:
            return True
        if data is not None or header_value_matcher is not None:
            return True
        return json is not UNDEFINED or json_contains is not UNDEFINED

    @staticmethod
    def _build_matcher(
        path: _ExpectArg,
        method: str | list[str],
        *,
        query_string: str | dict[str, str] | None,
        headers: dict[str, str] | None,
        json: Any,
        json_contains: Any,
        data: str | bytes | None,
        header_value_matcher: HeaderValueMatcher | None,
    ) -> _BaseMatcher:
        if isinstance(path, _BaseMatcher):
            if HTTPServerMock._has_extra_matcher_params(
                method,
                query_string,
                headers,
                json,
                json_contains,
                data,
                header_value_matcher,
            ):
                raise TypeError(
                    f"{_PREFIX} When passing a matcher as 'path', other "
                    "matching arguments (method, headers, json, …) are "
                    "silently ignored. Embed them in the matcher instead: "
                    "M(path=...) & M(method=...) & M(headers=...)."
                )
            return path
        return RequestMatcher(
            path,
            method,
            query_string=query_string,
            headers=headers,
            json=json,
            json_contains=json_contains,
            data=data,
            header_value_matcher=header_value_matcher,
        )

    @staticmethod
    def _parse_json(
        body: bytes,
    ) -> tuple[Any | None, str | None, bytes | None]:
        try:
            return json_module.loads(body), None, None
        except (json_module.JSONDecodeError, UnicodeDecodeError):
            return None, None, body


class BakedMock:
    """A ``HTTPServerMock`` wrapper with pre-filled request defaults."""

    def __init__(self, mock: HTTPServerMock, defaults: dict[str, Any]) -> None:
        self._mock = mock
        self._defaults = defaults

    def expect_request(
        self, path: _ExpectArg = None, **overrides: Any
    ) -> RequestHandler:
        """Register a permanent handler with baked defaults applied."""
        merged = {**self._defaults, **overrides}
        method = merged.pop("method", _DEFAULT_METHOD)
        return self._mock.expect_request(path, method, **merged)

    def expect_oneshot_request(
        self, path: _ExpectArg = None, **overrides: Any
    ) -> RequestHandler:
        """Register an oneshot handler with baked defaults applied."""
        merged = {**self._defaults, **overrides}
        method = merged.pop("method", _DEFAULT_METHOD)
        return self._mock.expect_oneshot_request(path, method, **merged)

    def expect_ordered_request(
        self, path: _ExpectArg = None, **overrides: Any
    ) -> RequestHandler:
        """Register an ordered handler with baked defaults applied."""
        merged = {**self._defaults, **overrides}
        method = merged.pop("method", _DEFAULT_METHOD)
        return self._mock.expect_ordered_request(path, method, **merged)
