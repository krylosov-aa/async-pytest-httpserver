from __future__ import annotations

import json as json_module
import re
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs

if TYPE_CHECKING:
    from aiohttp import web
    from multidict import CIMultiDictProxy, MultiDictProxy

    from .call_info import CallInfo

HeaderValueMatcher = Callable[[str, str, str], bool]


class _Undefined:
    """Sentinel for distinguishing "not provided" from None."""


UNDEFINED: _Undefined = _Undefined()


def _is_subset(expected: Any, actual: Any) -> bool:
    """Recursively check if expected is a subset of actual."""
    if isinstance(expected, dict) and isinstance(actual, dict):
        return all(
            key in actual and _is_subset(val, actual[key])
            for key, val in expected.items()
        )
    return expected == actual  # type: ignore[no-any-return]


class StartsWith:
    """Path lookup that matches when the request path starts with a prefix."""

    def __init__(self, value: str) -> None:
        self.value = value

    def __repr__(self) -> str:
        return f"StartsWith({self.value!r})"


class Contains:
    """Path lookup that matches when the request path contains a substring."""

    def __init__(self, value: str) -> None:
        self.value = value

    def __repr__(self) -> str:
        return f"Contains({self.value!r})"


_PathArg = str | re.Pattern[str] | StartsWith | Contains


class _BaseMatcher(ABC):
    """Abstract base for composable matchers. Supports &, |, ~ operators."""

    def __and__(self, other: _BaseMatcher) -> _And:
        return _And(self, other)

    def __or__(self, other: _BaseMatcher) -> _Or:
        return _Or(self, other)

    def __invert__(self) -> _Not:
        return _Not(self)

    @abstractmethod
    def matches(self, request: web.Request, body: bytes) -> bool:
        """Check whether a live request matches."""

    @abstractmethod
    def matches_call_info(self, call: CallInfo) -> bool:
        """Check whether a stored ``CallInfo`` matches."""


class _And(_BaseMatcher):
    """Matches when BOTH matchers match (logical AND)."""

    def __init__(self, left: _BaseMatcher, right: _BaseMatcher) -> None:
        self._left = left
        self._right = right

    def __repr__(self) -> str:
        return f"({self._left!r} & {self._right!r})"

    def matches(self, request: web.Request, body: bytes) -> bool:
        left_ok = self._left.matches(request, body)
        return left_ok and self._right.matches(request, body)

    def matches_call_info(self, call: CallInfo) -> bool:
        left_ok = self._left.matches_call_info(call)
        return left_ok and self._right.matches_call_info(call)


class _Or(_BaseMatcher):
    """Matches when EITHER matcher matches (logical OR)."""

    def __init__(self, left: _BaseMatcher, right: _BaseMatcher) -> None:
        self._left = left
        self._right = right

    def __repr__(self) -> str:
        return f"({self._left!r} | {self._right!r})"

    def matches(self, request: web.Request, body: bytes) -> bool:
        left_ok = self._left.matches(request, body)
        return left_ok or self._right.matches(request, body)

    def matches_call_info(self, call: CallInfo) -> bool:
        left_ok = self._left.matches_call_info(call)
        return left_ok or self._right.matches_call_info(call)


class _Not(_BaseMatcher):
    """Matches when the inner matcher does NOT match (logical NOT)."""

    def __init__(self, inner: _BaseMatcher) -> None:
        self._inner = inner

    def __repr__(self) -> str:
        return f"~{self._inner!r}"

    def matches(self, request: web.Request, body: bytes) -> bool:
        return not self._inner.matches(request, body)

    def matches_call_info(self, call: CallInfo) -> bool:
        return not self._inner.matches_call_info(call)


class RequestMatcher(_BaseMatcher):
    """
    Matches an incoming request against a set of registered criteria.

    ``M`` is a convenient alias for this class::

        from async_pytest_httpserver import M, StartsWith

        mock.expect_request(M(path=StartsWith("/api/")) & M(method="POST"))
    """

    def __init__(
        self,
        path: _PathArg | None = None,
        method: str | list[str] = "GET",
        *,
        query_string: str | dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        json: Any = UNDEFINED,
        json_contains: Any = UNDEFINED,
        data: str | bytes | None = None,
        header_value_matcher: HeaderValueMatcher | None = None,
    ) -> None:
        """
        Args:
            path: Exact string, ``re.Pattern``, ``StartsWith``, ``Contains``,
                or ``None`` for any path.
            method: ``"POST"``, ``["GET", "HEAD"]``, or ``"*"`` for any.
                Defaults to ``"GET"``.
            query_string: Dict or raw string. Extra request params are ignored.
                ``None`` accepts any.
            json: Exact JSON body match. Mutually exclusive with
                ``json_contains`` and ``data``.
            json_contains: Recursive subset match. Mutually exclusive with
                ``json`` and ``data``.
            data: Raw body — ``str`` is UTF-8 encoded before comparison.
        """
        json_set = not isinstance(json, _Undefined)
        json_contains_set = not isinstance(json_contains, _Undefined)
        if json_set and json_contains_set:
            raise TypeError("json and json_contains are mutually exclusive")
        if json_set and data is not None:
            raise TypeError("json and data are mutually exclusive")
        if json_contains_set and data is not None:
            raise TypeError("json_contains and data are mutually exclusive")
        self._path = path
        self._method = method
        self._query_string = query_string
        self._headers = headers
        self._json = json
        self._json_contains = json_contains
        self._data = data
        self._header_value_matcher = header_value_matcher

    def __repr__(self) -> str:
        parts = [f"path={self._path!r}", f"method={self._method!r}"]
        if self._query_string is not None:
            parts.append(f"query_string={self._query_string!r}")
        if self._headers is not None:
            parts.append(f"headers={self._headers!r}")
        if not isinstance(self._json, _Undefined):
            parts.append(f"json={self._json!r}")
        if not isinstance(self._json_contains, _Undefined):
            parts.append(f"json_contains={self._json_contains!r}")
        if self._data is not None:
            parts.append(f"data={self._data!r}")
        inner = ", ".join(parts)
        return f"RequestMatcher({inner})"

    def matches(self, request: web.Request, body: bytes) -> bool:
        if not self._match_path(request.path):
            return False
        if not self._match_method(request.method):
            return False
        if not self._match_query(request):
            return False
        if not self._match_headers(request):
            return False
        return self._match_body(body)

    def matches_call_info(self, call: CallInfo) -> bool:
        if not self._match_path(call.path):
            return False
        if not self._match_method(call.method):
            return False
        if not self._match_query_from_info(call.query):
            return False
        if not self._match_headers_from_info(call.headers):
            return False
        return self._match_body_from_info(call)

    def _match_path(self, path: str) -> bool:
        if self._path is None:
            return True
        if isinstance(self._path, re.Pattern):
            return bool(self._path.search(path))
        if isinstance(self._path, StartsWith):
            return path.startswith(self._path.value)
        if isinstance(self._path, Contains):
            return self._path.value in path
        return self._path == path

    def _match_method(self, method: str) -> bool:
        if isinstance(self._method, list):
            normalized = {meth.upper() for meth in self._method}
            return method.upper() in normalized
        if self._method == "*":
            return True
        return self._method.upper() == method.upper()

    def _match_query(self, request: web.Request) -> bool:
        if self._query_string is None:
            return True
        expected = self._parse_expected_query()
        actual = parse_qs(request.rel_url.query_string)
        return all(
            key in actual and actual[key] == val
            for key, val in expected.items()
        )

    def _match_query_from_info(self, query: MultiDictProxy[str]) -> bool:
        if self._query_string is None:
            return True
        expected = self._parse_expected_query()
        return all(
            query.getall(key, []) == val for key, val in expected.items()
        )

    def _parse_expected_query(self) -> dict[str, list[str]]:
        if isinstance(self._query_string, dict):
            return {name: [val] for name, val in self._query_string.items()}
        return parse_qs(self._query_string or "")

    def _match_headers(self, request: web.Request) -> bool:
        if self._headers is None:
            return True
        for key, expected_val in self._headers.items():
            actual_val = request.headers.get(key, "")
            if not self._compare_header(key, actual_val, expected_val):
                return False
        return True

    def _match_headers_from_info(self, headers: CIMultiDictProxy[str]) -> bool:
        if self._headers is None:
            return True
        for key, expected_val in self._headers.items():
            actual_val = headers.get(key, "")
            if not self._compare_header(key, actual_val, expected_val):
                return False
        return True

    def _compare_header(self, name: str, actual: str, expected: str) -> bool:
        if self._header_value_matcher is not None:
            return self._header_value_matcher(name, actual, expected)
        return actual == expected

    def _match_body(self, body: bytes) -> bool:
        if not isinstance(self._json, _Undefined):
            return self._match_json_body(body)
        if not isinstance(self._json_contains, _Undefined):
            return self._match_json_contains_body(body)
        if self._data is not None:
            raw = self._data
            expected = raw.encode() if isinstance(raw, str) else raw
            return body == expected
        return True

    def _match_body_from_info(self, call: CallInfo) -> bool:
        if not isinstance(self._json, _Undefined):
            return call.json == self._json  # type: ignore[no-any-return]
        if not isinstance(self._json_contains, _Undefined):
            return _is_subset(self._json_contains, call.json)
        if self._data is not None:
            raw = self._data
            expected = raw.encode() if isinstance(raw, str) else raw
            return self._call_raw_bytes(call) == expected
        return True

    @staticmethod
    def _call_raw_bytes(call: CallInfo) -> bytes:
        if call.data is not None:
            return call.data
        if call.text is not None:
            return call.text.encode("utf-8")
        return b""

    def _match_json_body(self, body: bytes) -> bool:
        try:
            actual = json_module.loads(body)
        except (json_module.JSONDecodeError, UnicodeDecodeError):
            return False
        return actual == self._json  # type: ignore[no-any-return]

    def _match_json_contains_body(self, body: bytes) -> bool:
        try:
            actual = json_module.loads(body)
        except (json_module.JSONDecodeError, UnicodeDecodeError):
            return False
        return _is_subset(self._json_contains, actual)


M = RequestMatcher
"""Alias for ``RequestMatcher``. Supports ``&``, ``|``, and ``~`` operators.

Example::

    from async_pytest_httpserver import M, StartsWith

    mock.expect_request(
        M(path=StartsWith("/api/")) & M(headers={"X-Auth": "token"})
    )
"""
