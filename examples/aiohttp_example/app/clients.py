from typing import Any, cast

import aiohttp


class WeatherClient:
    """Client for a hypothetical weather API."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    async def get_current(self, city: str) -> dict[str, Any]:
        async with (
            aiohttp.ClientSession() as session,
            session.get(
                f"{self.base_url}/weather",
                params={"city": city},
            ) as resp,
        ):
            resp.raise_for_status()
            return cast(dict[str, Any], await resp.json())

    async def get_forecast(self, city: str, days: int) -> list[dict[str, Any]]:
        async with (
            aiohttp.ClientSession() as session,
            session.get(
                f"{self.base_url}/forecast",
                params={"city": city, "days": str(days)},
            ) as resp,
        ):
            resp.raise_for_status()
            return cast(list[dict[str, Any]], await resp.json())

    async def report_alert(self, city: str, message: str) -> None:
        async with (
            aiohttp.ClientSession() as session,
            session.post(
                f"{self.base_url}/alerts",
                json={"city": city, "message": message},
            ) as resp,
        ):
            resp.raise_for_status()


class NotificationClient:
    """Client for a hypothetical notifications API."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    async def send(self, user_id: int, text: str) -> dict[str, Any]:
        async with (
            aiohttp.ClientSession() as session,
            session.post(
                f"{self.base_url}/notify",
                json={"user_id": user_id, "text": text},
            ) as resp,
        ):
            resp.raise_for_status()
            return cast(dict[str, Any], await resp.json())
