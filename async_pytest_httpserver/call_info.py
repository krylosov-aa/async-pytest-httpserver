from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterator

    from multidict import CIMultiDictProxy, MultiDictProxy


class _Unset:
    """Sentinel distinguishing 'not provided' from None."""


_UNSET: _Unset = _Unset()


@dataclass(frozen=True)
class CallInfo:
    """Immutable snapshot of a single incoming request.

    Attributes:
        method: HTTP method in uppercase, e.g. ``"POST"``.
        path: Request path, e.g. ``"/api/users"``.
        headers: Case-insensitive request headers.
        query: Parsed query parameters, e.g. ``call.query["page"]``.
        json: Parsed body for ``Content-Type: application/json`` requests.
            ``None`` if the body is empty or not JSON.
        text: Decoded body for ``Content-Type: text/plain`` requests.
            ``None`` if the body is empty or not plain text.
        data: Raw bytes for all other content types.
            ``None`` if the body is empty or was parsed as JSON/text.
    """

    method: str
    path: str
    headers: CIMultiDictProxy[str]
    query: MultiDictProxy[str]
    json: Any | None = None
    text: str | None = None
    data: bytes | None = None


class CallLog:
    """Per-handler call history with assertion helpers."""

    def __init__(self) -> None:
        self._calls: list[CallInfo] = []

    def __len__(self) -> int:
        return len(self._calls)

    def __getitem__(self, idx: int) -> CallInfo:
        return self._calls[idx]

    def __iter__(self) -> Iterator[CallInfo]:
        return iter(self._calls)

    @property
    def last(self) -> CallInfo:
        """Most recent call. Raises AssertionError if empty."""
        if not self._calls:
            raise AssertionError("No calls recorded — cannot get last")
        return self._calls[-1]

    def assert_called(self) -> None:
        """Assert called at least once."""
        if not self._calls:
            raise AssertionError("Expected at least 1 call, got 0")

    def assert_called_once(self) -> None:
        """Assert called exactly once."""
        if len(self._calls) != 1:
            raise AssertionError(f"Expected 1 call, got {len(self._calls)}")

    def assert_not_called(self) -> None:
        """Assert never called."""
        if self._calls:
            raise AssertionError(f"Expected 0 calls, got {len(self._calls)}")

    def assert_call_count(self, count: int) -> None:
        """Assert called exactly ``count`` times."""
        if len(self._calls) != count:
            raise AssertionError(
                f"Expected {count} call(s), got {len(self._calls)}"
            )

    def assert_called_with(
        self,
        *,
        call_index: int = -1,
        json: Any = _UNSET,
        text: Any = _UNSET,
        data: Any = _UNSET,
        headers: dict[str, str] | None = None,
        query: dict[str, str] | None = None,
    ) -> None:
        """
        Assert a specific call matches the given fields.

        All params are optional — only specified fields are verified.
        ``call_index=-1`` (default) checks the last call.
        ``data=`` checks ``call.data`` for binary bodies, or ``call.text``
        encoded as UTF-8 for ``text/plain``.
        """
        if not self._calls:
            raise AssertionError("No calls recorded")
        try:
            target = self._calls[call_index]
        except IndexError as exc:
            raise AssertionError(
                f"Call index {call_index} out of range "
                f"({len(self._calls)} call(s) recorded)"
            ) from exc
        self._check_json(target, json)
        self._check_text(target, text)
        self._check_data(target, data)
        self._check_headers(target, headers)
        self._check_query(target, query)

    def _append(self, call: CallInfo) -> None:
        self._calls.append(call)

    @staticmethod
    def _check_json(call: CallInfo, expected: Any) -> None:
        if isinstance(expected, _Unset):
            return
        if call.json != expected:
            raise AssertionError(
                f"Expected json={expected!r}, got {call.json!r}"
            )

    @staticmethod
    def _check_text(call: CallInfo, expected: Any) -> None:
        if isinstance(expected, _Unset):
            return
        if call.text != expected:
            raise AssertionError(
                f"Expected text={expected!r}, got {call.text!r}"
            )

    @staticmethod
    def _check_data(call: CallInfo, expected: Any) -> None:
        if isinstance(expected, _Unset):
            return
        if call.data is not None:
            actual: bytes | None = call.data
        elif call.text is not None:
            actual = call.text.encode("utf-8")
        else:
            actual = None
        if actual != expected:
            raise AssertionError(f"Expected data={expected!r}, got {actual!r}")

    @staticmethod
    def _check_headers(
        call: CallInfo, expected: dict[str, str] | None
    ) -> None:
        if expected is None:
            return
        for key, value in expected.items():
            actual = call.headers.get(key)
            if actual != value:
                raise AssertionError(
                    f"Expected header {key!r}={value!r}, got {actual!r}"
                )

    @staticmethod
    def _check_query(call: CallInfo, expected: dict[str, str] | None) -> None:
        if expected is None:
            return
        for key, value in expected.items():
            actual = call.query.get(key)
            if actual != value:
                raise AssertionError(
                    f"Expected query {key!r}={value!r}, got {actual!r}"
                )
