"""Application configuration — URLs read from environment variables."""

import os

WEATHER_API_URL: str = os.environ.get(
    "WEATHER_API_URL", "https://api.weather.example.com"
)
NOTIFY_API_URL: str = os.environ.get(
    "NOTIFY_API_URL", "https://api.notify.example.com"
)
