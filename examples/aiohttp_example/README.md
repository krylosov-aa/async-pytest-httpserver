## Example project

`examples/aiohttp_example/` is a self-contained project that demonstrates every feature of the library through realistic tests.

### Structure

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

### Running

```bash
uv sync    # creates .venv and installs the library from source
make test  # run all tests
```
