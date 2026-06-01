"""
Services that use URLs from config — the production code does NOT accept
the URL as a constructor parameter. This is the typical legacy or third-party
code pattern where URL injection requires monkeypatching.
"""

from typing import Any, cast

import aiohttp

from app import config


class WeatherService:
    """Uses config.WEATHER_API_URL — URL set at call time via config module."""

    @staticmethod
    async def current(city: str) -> dict[str, Any]:
        async with (
            aiohttp.ClientSession() as session,
            session.get(
                f"{config.WEATHER_API_URL}/weather",
                params={"city": city},
            ) as resp,
        ):
            resp.raise_for_status()
            return cast(dict[str, Any], await resp.json())

    @staticmethod
    async def forecast(city: str, days: int) -> list[dict[str, Any]]:
        async with (
            aiohttp.ClientSession() as session,
            session.get(
                f"{config.WEATHER_API_URL}/forecast",
                params={"city": city, "days": str(days)},
            ) as resp,
        ):
            resp.raise_for_status()
            return cast(list[dict[str, Any]], await resp.json())


class NotifyService:
    """
    Uses a class-level BASE_URL constant — a common pattern when the URL
    is configured once at class definition time.
    """

    BASE_URL: str = "https://api.notify.example.com"

    async def send(self, user_id: int, text: str) -> dict[str, Any]:
        async with (
            aiohttp.ClientSession() as session,
            session.post(
                f"{self.BASE_URL}/notify",
                json={"user_id": user_id, "text": text},
            ) as resp,
        ):
            resp.raise_for_status()
            return cast(dict[str, Any], await resp.json())
