# async-pytest-httpserver
[![PyPI](https://img.shields.io/pypi/v/async-pytest-httpserver.svg)](https://pypi.org/project/async-pytest-httpserver/)
[![PyPI Downloads](https://static.pepy.tech/personalized-badge/async-pytest-httpserver?period=total&units=INTERNATIONAL_SYSTEM&left_color=BLACK&right_color=GREEN&left_text=downloads)](https://pepy.tech/projects/async-pytest-httpserver)

No AI was used in the creation of this library.

async-pytest-httpserver is a fully asynchronous mock HTTP server for pytest,
built on top of aiohttp.

It is designed for testing code that makes HTTP requests
(via aiohttp, httpx, requests, etc.) without depending on real external
services.

Features
- Fully asynchronous — implemented using aiohttp
- Dynamic runtime mocking — add or modify mock routes while the server is running
- Seamless pytest integration — works smoothly with pytest-aiohttp and pytest-asyncio
- Real TCP server — compatible with any HTTP client (aiohttp, httpx, requests, etc.)
- Supports async handlers — easily define coroutine-based responses
- Flexible mock responses — either return a Response object or a handler that produces one

## How to use

### 1. fixture for start mock server

```python
from async_pytest_httpserver import (
    MockData,
    AddMockDataFunc,
)

@pytest_asyncio.fixture
async def some_service_mock(
    external_service_mock: Callable[
        [], Awaitable[tuple[str, AddMockDataFunc]]
    ],
) -> AsyncGenerator[AddMockDataFunc, None]:
    url, add_mock_data = await external_service_mock()
    old_url = settings.EXTERNAL_SERVICE_URL
    settings.EXTERNAL_SERVICE_URL = url
    try:
        yield add_mock_data
    finally:
        settings.EXTERNAL_SERVICE_URL = old_url
```

### 2. mock and test it

#### static mock

```python
import pytest
from http import HTTPStatus
from async_pytest_httpserver import (
    MockData,
)
from aiohttp.web import json_response, Request, Response


@pytest.mark.asyncio
async def test_static_mock(client, some_service_mock):
    # Arrange
    response = json_response(
        {"result": "some_result"},
        status=HTTPStatus.OK,
    )
    calls_info = some_service_mock(MockData("POST", "/some_api", response))

    # Act
    response = await client.post(
        f"{settings.EXTERNAL_SERVICE_URL}/some_api",
        json={"text": "text"},
    )

    # Assert
    assert response.ok
    data = await response.json()
    assert data["result"] == "some_result"

    assert len(calls_info) == 1
    call_info = calls_info[0]
    assert call_info["json"] == {"text": "text"}
```

#### dynamic async mock

```python
import pytest
from http import HTTPStatus
from async_pytest_httpserver import (
    MockData,
)
from aiohttp.web import json_response, Request, Response


async def async_mock_handler(request: Request) -> Response:
    return json_response(
        {"result": "some_result"},
        status=HTTPStatus.OK,
    )


@pytest.mark.asyncio
async def test_async_handler(client, some_service_mock):
    # Arrange
    calls_info = some_service_mock(
        MockData("POST", "/some_api", async_mock_handler)
    )

    # Act
    response = await client.post(
        f"{settings.EXTERNAL_SERVICE_URL}/some_api",
        json={"text": "text"},
    )

    # Assert
    assert response.ok
    data = await response.json()
    assert data["result"] == "some_result"

    assert len(calls_info) == 1
    call_info = calls_info[0]
    assert call_info["json"] == {"text": "text"}
```

#### dynamic sync mock

```python
import pytest
from http import HTTPStatus
from async_pytest_httpserver import (
    MockData,
)
from aiohttp.web import json_response, Request, Response

def sync_mock_handler(request: Request) -> Response:
    return json_response(
        {"result": "some_result"},
        status=HTTPStatus.OK,
    )


@pytest.mark.asyncio
async def test_sync_handler(client, some_service_mock):
    # Arrange
    calls_info = some_service_mock(
        MockData("POST", "/some_api", sync_mock_handler)
    )

    # Act
    response = await client.post(
        f"{settings.EXTERNAL_SERVICE_URL}/some_api",
        json={"text": "text"},
    )

    # Assert
    assert response.ok
    data = await response.json()
    assert data["result"] == "some_result"

    assert len(calls_info) == 1
    call_info = calls_info[0]
    assert call_info["json"] == {"text": "text"}
```

## mock data types

### 1. just aiohttp.web.Response

for example:

```python
from aiohttp.web import json_response

json_response(
    {"result": "some_result"},
    status=HTTPStatus.OK,
)
```

### 2. callable

If you need custom behavior instead of a static response,
you can provide a callable (func or async func) that returns a
aiohttp.web.Response.

It must match the following signature:

```python
ResponseHandler = Callable[
    [web.Request], web.Response | Awaitable[web.Response]
]
```
