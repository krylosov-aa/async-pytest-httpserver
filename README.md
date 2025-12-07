# async-pytest-httpserver
[![PyPI](https://img.shields.io/pypi/v/async-pytest-httpserver.svg)](https://pypi.org/project/async-pytest-httpserver/)
[![PyPI Downloads](https://static.pepy.tech/personalized-badge/async-pytest-httpserver?period=total&units=INTERNATIONAL_SYSTEM&left_color=BLACK&right_color=GREEN&left_text=downloads)](https://pepy.tech/projects/async-pytest-httpserver)

No AI was used in the creation of this library.

async-pytest-httpserver is a fully asynchronous mock HTTP server for use in pytest tests, built on top of aiohttp.

It is designed for testing code that performs HTTP requests (aiohttp, httpx, requests, etc.) without relying on real external services.

## Features
- Fully asynchronous - implemented using aiohttp.web.Application
- Dynamic runtime mocking - add or modify mock routes while the server is running
- Seamless integration with pytest-aiohttp and pytest-asyncio
- Real TCP server - works with any HTTP client (aiohttp, httpx, requests, etc.)
- Supports async handlers - easily define coroutine-based responses
