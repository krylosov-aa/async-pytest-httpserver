# async-pytest-httpserver

[![PyPI](https://img.shields.io/pypi/v/async-pytest-httpserver.svg)](https://pypi.org/project/async-pytest-httpserver/)
[![PyPI Downloads](https://static.pepy.tech/personalized-badge/async-pytest-httpserver?period=total&units=INTERNATIONAL_SYSTEM&left_color=BLACK&right_color=GREEN&left_text=downloads)](https://pepy.tech/projects/async-pytest-httpserver)


Fully async mock HTTP server for pytest — test HTTP clients against a real TCP server on localhost, with rich request matching and response control.

## Quick start

An application that calls a payment API:

```python
# my_app/settings.py
PAYMENT_URL = "https://api.payments.example.com"
```

```python
# my_app/payment.py
import aiohttp
from my_app import settings

async def charge(amount: int) -> dict:
    """Call the external payment API and return the response JSON."""
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{settings.PAYMENT_URL}/charge",
            json={"amount": amount},
        ) as resp:
            resp.raise_for_status()
            return await resp.json()
```

Set up a fixture that redirects the URL to the mock server:

```python
# tests/conftest.py
import pytest_asyncio
from my_app import settings

@pytest_asyncio.fixture
async def payment_mock(http_server, monkeypatch):
    mock = await http_server()
    monkeypatch.setattr(settings, "PAYMENT_URL", mock.base_url)
    yield mock
```

```python
# tests/test_payment.py
from my_app.payment import charge

async def test_charge_sends_correct_payload(payment_mock):
    # Arrange
    handler = payment_mock.expect_request("/charge", method="POST")
    handler.respond_with_json({"transaction_id": "tx-42"}, status=201)

    # Act
    result = await charge(amount=100)

    # Assert
    assert result["transaction_id"] == "tx-42"
    handler.call_log.assert_called_once()
    handler.call_log.assert_called_with(json={"amount": 100})
```

## Functionality

### Fixture setup

`http_server` is a factory fixture — call it once per external service you want to mock:

```python
# tests/conftest.py
import pytest_asyncio
from my_app import settings

@pytest_asyncio.fixture
async def payment_mock(http_server, monkeypatch):
    mock = await http_server()
    monkeypatch.setattr(settings, "PAYMENT_URL", mock.base_url)
    yield mock
```

`mock.base_url` contains the server address, e.g. `http://127.0.0.1:54321/`.

`monkeypatch.setattr` injects the mock server url instead of the real one for the duration of the test

### Registering handlers

```python
handler = mock.expect_request("/api/users", method="POST")
handler.respond_with_json({"id": 1}, status=201)
```

`expect_request` returns a `RequestHandler`. Use it to configure the response and later inspect what was called.

### Response types

#### respond_with_json

```python
handler.respond_with_json({"users": []})
handler.respond_with_json({"error": "not found"}, status=404)
handler.respond_with_json({"ok": True}, headers={"X-Request-Id": "abc"})
```

#### respond_with_data

```python
handler.respond_with_data("pong")
handler.respond_with_data("<root/>", content_type="application/xml", status=200)
handler.respond_with_data("", status=204)
```

#### respond_with_response

Pass any pre-built `aiohttp.web.Response`:

```python
from aiohttp.web import Response, json_response

handler.respond_with_response(Response(status=202, text="accepted"))
handler.respond_with_response(json_response({"id": 1}, status=201))
```

#### respond_with_handler

For dynamic responses that inspect the incoming request:

```python
async def my_handler(request):
    body = await request.json()
    return json_response({"echo": body["message"]})

handler.respond_with_handler(my_handler)
```

Sync handlers work too:

```python
def my_handler(request):
    return Response(text="ok")

handler.respond_with_handler(my_handler)
```

#### respond_with_sequence

Return different responses on successive calls. The last item persists for all subsequent calls. Useful for testing retry logic:

```python
handler.respond_with_sequence([
    (503, {"error": "unavailable"}),  # 1st call
    (503, {"error": "unavailable"}),  # 2nd call
    (200, {"data": "ready"}),         # 3rd+ calls (repeats)
])
```

Accepts `web.Response` objects, `(status, json)` tuples, and callables — or a mix:

```python
from aiohttp.web import Response

handler.respond_with_sequence([
    Response(status=429, text="rate limited"),
    (200, {"result": "ok"}),
])
```

### Request matching

All matching parameters are passed to `expect_request` as keyword arguments.

#### Path

Exact string:

```python
mock.expect_request("/api/users")
```

Regular expression:

```python
import re

mock.expect_request(re.compile(r"^/api/users/\d+$"))
```

Starts with a prefix:

```python
from async_pytest_httpserver import StartsWith

mock.expect_request(path=StartsWith("/api/"))
```

Contains a substring:

```python
from async_pytest_httpserver import Contains

mock.expect_request(path=Contains("/users/"))
```

#### Method

Single method:

```python
mock.expect_request("/resource", method="POST")
```

List of methods:

```python
mock.expect_request("/resource", method=["GET", "HEAD"])
```

Any method:

```python
mock.expect_request("/health", method="*")
```

#### Query string

As a dict (parameter order doesn't matter, extra parameters in the request are ignored):

```python
mock.expect_request("/search", query_string={"q": "python", "page": "1"})
# Matches /search?page=1&q=python
# Also matches /search?q=python&page=1&source=google (extra params ignored)
```

As a raw string:

```python
mock.expect_request("/items", query_string="sort=asc&limit=10")
```

#### Headers

All specified headers must be present with the given values:

```python
mock.expect_request("/secure", headers={"X-Api-Key": "secret"})
```

Custom comparison function `(header_name, actual, expected) -> bool`:

```python
def starts_with_bearer(name, actual, expected):
    return actual.startswith(expected)

mock.expect_request(
    "/auth",
    headers={"Authorization": "Bearer "},
    header_value_matcher=starts_with_bearer,
)
```

#### JSON body

Exact match:

```python
mock.expect_request("/users", method="POST", json={"name": "Alice"})
```

#### Partial JSON matching

Match requests whose body **contains** the given keys — recursive subset check:

```python
mock.expect_request(
    "/events",
    method="POST",
    json_contains={"user": {"name": "Alice"}},
)
# Matches {"user": {"name": "Alice", "role": "admin"}, "meta": {...}}
```

#### Raw data

```python
mock.expect_request("/upload", data=b"\xff\xd8\xff")  # bytes
mock.expect_request("/text", data="hello world")      # string
```

#### Combinators

`M` is an alias for `RequestMatcher`. Combine matchers with `&` (AND), `|` (OR), `~` (NOT):

```python
from async_pytest_httpserver import M, StartsWith

# OR — match either path
mock.expect_request(
    M(path="/api/v1", method="GET") | M(path="/api/v2", method="GET")
)

# AND — path prefix AND required header
mock.expect_request(
    M(path=StartsWith("/api/"), method="GET") & M(headers={"X-Auth": "token"})
)

# NOT — exclude health check path
mock.expect_request(~M(path=StartsWith("/health")), method="GET")

# Complex combinations
mock.expect_request(
    (M(path="/v1", method="*") | M(path="/v2", method="*"))
    & M(method="POST")
)
```

### Handler lifetime

#### Permanent

`expect_request` — responds to every matching request indefinitely.

```python
handler = mock.expect_request("/api", method="GET")
handler.respond_with_json({"ok": True})
```

#### Oneshot

`expect_oneshot_request` — responds exactly once. Subsequent calls get 404.

```python
handler = mock.expect_oneshot_request("/init", method="POST")
handler.respond_with_json({"initialized": True})

r1 = await client.post(mock.url_for("/init"))  # 200
r2 = await client.post(mock.url_for("/init"))  # 404 — handler is gone

handler.call_log.assert_called_once()
```

Call `mock.check()` at the end of a test to assert that all oneshot handlers were actually consumed:

```python
mock.check()  # raises if any oneshot/ordered handlers were never called
```

#### Ordered

`expect_ordered_request` — handlers must be invoked in registration order. Violating the order returns 500.

```python
h1 = mock.expect_ordered_request("/step1", method="POST")
h1.respond_with_json({"step": 1})

h2 = mock.expect_ordered_request("/step2", method="POST")
h2.respond_with_json({"step": 2})

await client.post(mock.url_for("/step1"))
await client.post(mock.url_for("/step2"))

mock.check()  # passes — both consumed in order
```

### Conflict policy

When two handlers are registered for overlapping routes, `ConflictPolicy` controls which one wins or whether registration raises an error.

Pass `conflict_policy` to the `http_server` factory:

```python
from async_pytest_httpserver import ConflictPolicy

mock = await http_server(conflict_policy=ConflictPolicy.LAST_WINS)
```

#### LAST_WINS (default)

The most recently registered handler takes priority. Earlier handlers remain in the pool as fallbacks for non-overlapping requests.

```python
mock = await http_server()

mock.expect_request("/api", method="GET").respond_with_json({"v": 1})
mock.expect_request("/api", method="GET").respond_with_json({"v": 2})

resp = await client.get(mock.url_for("/api"))
data = await resp.json()
assert data == {"v": 2}
```

#### FIRST_WINS

The first registered handler keeps priority. Later registrations for the same route are checked after the first one.

```python
mock = await http_server(conflict_policy=ConflictPolicy.FIRST_WINS)

mock.expect_request("/api", method="GET").respond_with_json({"v": 1})
mock.expect_request("/api", method="GET").respond_with_json({"v": 2})

resp = await client.get(mock.url_for("/api"))
data = await resp.json()
assert data == {"v": 1}
```

#### ERROR

Raises `ConflictError` at registration time if the new handler overlaps with an already-registered one in the same pool. Useful for catching accidental duplicate registrations.

```python
from async_pytest_httpserver import ConflictPolicy, ConflictError

mock = await http_server(conflict_policy=ConflictPolicy.ERROR)
mock.expect_request("/api", method="GET").respond_with_json({"v": 1})

# Raises ConflictError — same path and method already registered
mock.expect_request("/api", method="GET").respond_with_json({"v": 2})
```

Overlap detection is field-by-field: two matchers are considered non-overlapping when at least one dimension is provably incompatible (different exact paths, disjoint methods, different concrete query or header values, different JSON bodies). Conservative matchers (`StartsWith`, `Contains`, regex, `json_contains=`, composites) are treated as potentially overlapping.

Cross-pool registrations — e.g. an oneshot handler alongside a permanent one for the same route — are allowed regardless of policy.

### Assertions

#### CallLog

Every handler tracks its calls in `.call_log`:

```python
handler.call_log.assert_called()           # at least once
handler.call_log.assert_called_once()      # exactly once
handler.call_log.assert_not_called()       # never
handler.call_log.assert_call_count(3)      # exactly 3 times
```

Check what was sent with `assert_called_with`. All parameters are keyword-only and optional — only specified fields are verified:

```python
handler.call_log.assert_called_with(json={"name": "Alice"})
handler.call_log.assert_called_with(query={"page": "2"})
handler.call_log.assert_called_with(headers={"X-Api-Key": "secret"})
handler.call_log.assert_called_with(text="hello")

# Check a specific call by index (-1 = last, 0 = first)
handler.call_log.assert_called_with(call_index=0, json={"name": "Alice"})
handler.call_log.assert_called_with(call_index=1, json={"name": "Bob"})
```

Access `CallInfo` objects directly:

```python
call = handler.call_log[0]    # first
call = handler.call_log[-1]   # last
call = handler.call_log.last  # last (raises if empty)

call.method    # "POST"
call.path      # "/api/users"
call.headers   # CIMultiDictProxy (case-insensitive header access)
call.query     # MultiDictProxy — e.g. call.query["page"]
call.json      # parsed body for application/json requests
call.text      # decoded body for text/plain requests
call.data      # raw bytes for all other content types
```

Iterate all calls:

```python
for call in handler.call_log:
    assert call.json["amount"] > 0
```

#### Server-level log

`mock.log` records every request across all handlers as `(CallInfo, Response)` pairs:

```python
assert len(mock.log) == 3

call, response = mock.log[0]
assert call.path == "/api/users"
```

Query the log using any matcher:

```python
from async_pytest_httpserver import M, StartsWith

mock.assert_request_made(
    M(path=StartsWith("/api/"), method="POST"),
    count=2,
)

for call, response in mock.iter_matching_requests(M(path="/api/users")):
    print(call.json)
```

#### check()

`mock.check()` asserts at the end of a test that:

- no exceptions were raised inside handlers
- all oneshot handlers were consumed
- all ordered handlers were consumed

To also verify that **permanent** handlers were called at least once:

```python
mock.check(all_called=True)
```

Inspect handler errors explicitly:

```python
mock.check_handler_errors()  # re-raises first exception from a handler
```

### Hooks

Post-hooks transform the response after it's built. Attach with `with_post_hook()` — returns `self` for chaining:

```python
handler.with_post_hook(Delay(ms=500)).respond_with_json({"slow": True})
```

Multiple hooks are applied in registration order.

#### Delay

Pause before sending the response — useful for testing timeouts or loading states:

```python
from async_pytest_httpserver import Delay

handler.with_post_hook(Delay(ms=500))   # wait 500ms
# or
handler.with_post_hook(Delay(sec=0.5))  # wait 500ms
```

#### Garbage

Corrupt the response body with random bytes — for testing error-handling code:

```python
from async_pytest_httpserver import Garbage

handler.with_post_hook(Garbage(prefix_size=4, suffix_size=2))
# Prepends 4 random bytes, appends 2 random bytes
```

#### Chain

Compose multiple hooks in sequence:

```python
from async_pytest_httpserver import Chain, Delay, Garbage

handler.with_post_hook(Chain(Delay(ms=100), Garbage(suffix_size=3)))
```

#### Custom hook

Any callable matching `(request, response) -> response` works, sync or async:

```python
async def add_trace_header(request, response):
    response.headers["X-Trace-Id"] = request.headers.get("X-Request-Id", "")
    return response

handler.with_post_hook(add_trace_header)
```

### Utilities

#### url_for()

Build a full URL for a path:

```python
mock.url_for("/api/users/42")
# "http://127.0.0.1:54321/api/users/42"
```

#### clear()

Remove all handlers and reset call history. The server keeps running:

```python
mock.clear()
```

Useful for shared fixtures that run multiple scenarios:

```python
async def test_two_scenarios(mock):
    mock.expect_request("/api").respond_with_json({"v": 1})
    # ... first scenario ...

    mock.clear()

    mock.expect_request("/api").respond_with_json({"v": 2})
    # ... second scenario ...
```

#### format_matchers()

Human-readable summary of all registered handlers — for debugging:

```python
print(mock.format_matchers())
# Registered handlers:
#   [PERMANENT] RequestMatcher(path='/api/users', method='GET') — 2 call(s)
#   [ONESHOT]   RequestMatcher(path='/init', method='POST') — 0 call(s)
```

#### bake()

Create a pre-configured wrapper with shared defaults. Defaults can be overridden per-call:

```python
# All handlers on this mock use POST and require the auth header
api = mock.bake(method="POST", headers={"Authorization": "Bearer token"})

api.expect_request("/users").respond_with_json({"id": 1})
api.expect_request("/orders").respond_with_json({"id": 2})

# Override per-call — this handler uses GET
api.expect_request("/health", method="GET").respond_with_json({"ok": True})
```

### Example project

[examples/aiohttp_example/](examples/aiohttp_example) is a self-contained project that demonstrates every feature of the library through realistic tests.

#### Structure

```
examples/aiohttp_example/
  app/
    clients.py         # WeatherClient, NotificationClient — real HTTP clients
    services.py        # Services that read URLs from config (for injection demos)
    config.py          # Module-level URL config (env-var based)
  tests/
    conftest.py        # Fixtures: mock, weather_mock, notify_mock, client
    test_responses.py  # All response types: json, data, handler, sequence
    test_matching.py   # All matching: path, method, query, headers, body, M()
    test_assertions.py # CallLog, server log, check(), assert_request_made
    test_lifetime.py   # Permanent, oneshot, ordered, sequences, bake()
    test_hooks.py      # Delay, Garbage, Chain, custom hooks
    test_url_injection.py  # URL injection via monkeypatch (3 patterns)
```

#### Running

```bash
cd examples/aiohttp_example
uv sync    # creates .venv and installs the library from source
make test  # run all tests
```

### Multiple mock servers

Call `http_server()` multiple times in one fixture to mock several external services independently:

```python
@pytest_asyncio.fixture
async def services(http_server, monkeypatch):
    payments = await http_server()
    notifications = await http_server()
    monkeypatch.setattr(settings, "PAYMENT_URL", payments.base_url)
    monkeypatch.setattr(settings, "NOTIFY_URL", notifications.base_url)
    yield payments, notifications


async def test_checkout(client, services):
    # Arrange
    payments, notifications = services

    payments.expect_request("/charge", method="POST").respond_with_json({"ok": True})
    notifications.expect_request("/send", method="POST").respond_with_json({"ok": True})

    # Act
    await client.post(f"{settings.CHECKOUT_URL}/buy", json={"item_id": 1})

    # Assert
    payments.check()
    notifications.check()
```
