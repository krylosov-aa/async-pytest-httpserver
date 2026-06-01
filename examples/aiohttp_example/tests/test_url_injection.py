"""
URL injection patterns — how to point production code at a mock server.

The library creates a real TCP server and returns its address in mock.base_url.
The challenge: production code usually reads the URL from config, environment
variables, or a class attribute — not from a constructor parameter.
This file shows three common injection patterns using pytest's monkeypatch.
"""

from collections.abc import Awaitable, Callable

import pytest
from async_pytest_httpserver import HTTPServerMock

from app import config
from app.services import NotifyService, WeatherService

_MockFactory = Callable[[], Awaitable[HTTPServerMock]]


@pytest.fixture
async def weather_mock(
    http_server: _MockFactory, monkeypatch: pytest.MonkeyPatch
) -> HTTPServerMock:
    mock = await http_server()
    # Replace the config attribute that WeatherService reads at call time.
    monkeypatch.setattr(config, "WEATHER_API_URL", mock.base_url)
    return mock


async def test_current_weather_via_config(weather_mock: HTTPServerMock):
    """
    Production code reads the URL from a module-level variable in config.py.
    monkeypatch.setattr replaces it for the duration of the test and restores
        the original value automatically on teardown.
    """
    # Arrange
    handler = weather_mock.expect_request(
        "/weather", method="GET", query_string={"city": "Oslo"}
    )
    handler.respond_with_json({"city": "Oslo", "temp": 5})

    # Act
    result = await WeatherService().current("Oslo")

    # Assert
    assert result["temp"] == 5
    handler.call_log.assert_called_once()


async def test_forecast_via_config(weather_mock: HTTPServerMock):
    """
    Production code reads the URL from a module-level variable in config.py.
    monkeypatch.setattr replaces it for the duration of the test and restores
        the original value automatically on teardown.
    """
    # Arrange
    handler = weather_mock.expect_request(
        "/forecast", method="GET", query_string={"city": "Oslo", "days": "3"}
    )
    handler.respond_with_json([{"day": 1}, {"day": 2}, {"day": 3}])

    # Act
    forecast = await WeatherService().forecast("Oslo", days=3)

    # Assert
    assert len(forecast) == 3
    handler.call_log.assert_called_once()


async def test_config_is_restored_after_test(weather_mock: HTTPServerMock):
    """
    The original config value is still intact inside this test (it was
        patched in the fixture). After the test ends, monkeypatch restores it.
    """
    assert weather_mock.base_url == config.WEATHER_API_URL


async def test_env_var_injection(
    http_server: _MockFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Production code calls os.environ.get("WEATHER_API_URL") at call time,
    not at import time. monkeypatch.setenv sets the env var; monkeypatch
    restores it after the test.

    If the URL is read at *import* time (module-level assignment), use
    monkeypatch.setattr on the module variable instead (Pattern 1),
    because setenv won't affect values already assigned to variables.
    """
    # Arrange
    mock: HTTPServerMock = await http_server()
    monkeypatch.setenv("WEATHER_API_URL", mock.base_url)
    # Re-read config so it picks up the new env var.
    monkeypatch.setattr(config, "WEATHER_API_URL", mock.base_url)

    handler = mock.expect_request("/weather", method="GET")
    handler.respond_with_json({"city": "Berlin", "temp": 18})

    # Act
    result = await WeatherService().current("Berlin")

    # Assert
    assert result["city"] == "Berlin"
    handler.call_log.assert_called_once()


@pytest.fixture
async def notify_mock(
    http_server: _MockFactory, monkeypatch: pytest.MonkeyPatch
) -> HTTPServerMock:
    mock = await http_server()
    # Replace the class attribute — affects all instances of NotifyService.
    monkeypatch.setattr(NotifyService, "BASE_URL", mock.base_url)
    return mock


async def test_notify_via_class_attribute(notify_mock: HTTPServerMock):
    """
    Production code has BASE_URL as a class attribute. monkeypatch.setattr
        on the class replaces it for all instances created during the test.
    """
    # Arrange
    handler = notify_mock.expect_request("/notify", method="POST")
    handler.respond_with_json({"sent": True})

    # Act — NotifyService() reads BASE_URL from the class, not a constructor
    result = await NotifyService().send(user_id=7, text="Hello")

    # Assert
    assert result["sent"] is True
    handler.call_log.assert_called_once()
    handler.call_log.assert_called_with(json={"user_id": 7, "text": "Hello"})


async def test_class_attribute_restored_after_test():
    """
    After notify_mock fixture tears down, BASE_URL is back to the original.
    """
    assert NotifyService.BASE_URL == "https://api.notify.example.com"


async def test_two_services_patched_independently(
    http_server: _MockFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Two services, two mocks — each patched independently.
    An endpoint that calls both weather and notify APIs.
    Each service is patched to its own mock server.
    """
    # Arrange
    weather: HTTPServerMock = await http_server()
    notify: HTTPServerMock = await http_server()

    monkeypatch.setattr(config, "WEATHER_API_URL", weather.base_url)
    monkeypatch.setattr(NotifyService, "BASE_URL", notify.base_url)

    weather.expect_request("/weather", method="GET").respond_with_json(
        {"city": "Rome", "temp": 30, "alert": True}
    )

    notify.expect_request("/notify", method="POST").respond_with_json(
        {"sent": True}
    )

    # Act
    data = await WeatherService().current("Rome")
    if data.get("alert"):
        await NotifyService().send(user_id=1, text=f"Alert in {data['city']}")

    # Assert
    weather.check()
    notify.check()
