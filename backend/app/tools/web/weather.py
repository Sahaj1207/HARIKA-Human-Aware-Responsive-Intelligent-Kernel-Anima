"""Weather now and for the coming week, from Open-Meteo (free, no account or key).

Places are found with Open-Meteo's geocoder. "Here" is the home city from
Settings, or else the computer's approximate location from its IP address.
"""
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional, Tuple

import httpx

from app.core.daily_settings import daily_settings
from app.core.dates import day_offset
from app.tools.base_tool import BaseTool
from app.tools.registry import tool_registry
from app.tools.schemas import PermissionLevel, ToolHealth, ToolManifest

# WMO weather interpretation codes (the forecast API's data format).
_CONDITIONS = {
    0: "clear", 1: "mostly clear", 2: "partly cloudy", 3: "overcast", 45: "foggy", 48: "foggy",
    51: "light drizzle", 53: "drizzle", 55: "heavy drizzle", 56: "freezing drizzle", 57: "freezing drizzle",
    61: "light rain", 63: "rain", 65: "heavy rain", 66: "freezing rain", 67: "freezing rain",
    71: "light snow", 73: "snow", 75: "heavy snow", 77: "snow grains",
    80: "light showers", 81: "showers", 82: "heavy showers", 85: "snow showers", 86: "heavy snow showers",
    95: "thunderstorms", 96: "thunderstorms with hail", 99: "thunderstorms with hail",
}
_HERE = {"", "here", "my location", "current location", "outside", "today", "home"}
_IP_CACHE_SECONDS = 6 * 3600


@dataclass
class Place:
    name: str
    latitude: float
    longitude: float
    country_code: str = ""


class PlaceNotFound(LookupError):
    pass


class _Locator:
    def __init__(self):
        self._ip_place: Optional[Place] = None
        self._ip_time = 0.0

    async def resolve(self, requested: str) -> Place:
        name = (requested or "").strip()
        if name.lower() in _HERE:
            home = daily_settings.load()["home"]
            return await self.geocode(home) if home else await self.approximate()
        return await self.geocode(name)

    async def geocode(self, name: str) -> Place:
        async with httpx.AsyncClient(timeout=8.0) as client:
            data = (await client.get("https://geocoding-api.open-meteo.com/v1/search",
                                     params={"name": name.split(",")[0].strip(), "count": 5})).json()
        results = data.get("results") or []
        # "Paris, Texas": prefer the result whose region or country matches the qualifier.
        qualifier = name.split(",", 1)[1].strip().lower() if "," in name else ""
        if qualifier:
            results = [r for r in results if qualifier in f"{r.get('admin1', '')} {r.get('country', '')} {r.get('country_code', '')}".lower()] or results
        if not results:
            raise PlaceNotFound(name)
        best = results[0]
        return Place(best["name"], best["latitude"], best["longitude"], best.get("country_code", ""))

    async def approximate(self) -> Place:
        if self._ip_place and time.time() - self._ip_time < _IP_CACHE_SECONDS:
            return self._ip_place
        async with httpx.AsyncClient(timeout=8.0) as client:
            data = (await client.get("https://ipwho.is/")).json()
        if not data.get("success"):
            raise PlaceNotFound("your location")
        self._ip_place = Place(data.get("city") or data.get("region") or "your area",
                               data["latitude"], data["longitude"], data.get("country_code", ""))
        self._ip_time = time.time()
        return self._ip_place

    async def country_code(self) -> str:
        try:
            return (await self.resolve("here")).country_code or "US"
        except Exception:
            return "US"


locator = _Locator()


class WeatherTool(BaseTool):
    manifest = ToolManifest(
        name="weather",
        display_name="Weather",
        description="Tells the current weather and the forecast for the next week, anywhere.",
        version="1.0.0",
        author="HARIKA OS Core",
        category="web",
        permissions=PermissionLevel.NONE,
        enabled=True,
        platforms=["windows", "linux", "darwin"],
        capabilities=["weather"],
        operations={"weather": "weather"},
        free_text_operations=["weather"],
        default_targets={"weather": "here"},
        ability="tell you the weather and forecast",
        target_description=(
            "the place (city), or 'here' for the user's own location; "
            "parameters.day: 'today', 'tomorrow', a weekday name or 'YYYY-MM-DD' (within a week)"
        ),
    )
    timeout_seconds = 20.0

    def health_check(self) -> ToolHealth:
        return ToolHealth(available=True, reason="Open-Meteo", dependencies=["httpx"])

    def match_target(self, requested: str, operation: Optional[str] = None) -> Tuple[Optional[str], float]:
        return ((requested or "").strip() or "here"), 0.8

    def describe_action(self, args: Dict[str, Any]) -> str:
        place = str(args.get("target") or "here").strip()
        where = "" if place.lower() in ("here", "") else f" in {place}"
        day = str(args.get("day") or "").strip().lower()
        return f"check the weather{where}" + (f" for {day}" if day and day != "today" else "")

    async def execute(self, args: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
        target = str(args.get("target") or "here")
        offset = day_offset(args.get("day"), date.today())
        if offset is None or not 0 <= offset <= 6:
            return self._fail("I can only see the weather for the next 7 days")
        if dry_run:
            return {"dry_run": True, "action": "weather", "place": target, "day": offset}
        try:
            place = await locator.resolve(target)
            report = await self.report(place, offset)
        except PlaceNotFound as missing:
            return self._fail(f"I couldn't find a place called {missing}")
        except Exception:
            return self._fail("I couldn't reach the weather service. Check your internet connection")
        return {"action": "weather", "place": place.name, "success": True, "verified": True,
                "summary": report["summary"], "weather": report, "error": None}

    async def report(self, place: Place, offset: int = 0) -> Dict[str, Any]:
        fahrenheit = place.country_code.upper() == "US"
        async with httpx.AsyncClient(timeout=8.0) as client:
            data = (await client.get("https://api.open-meteo.com/v1/forecast", params={
                "latitude": place.latitude, "longitude": place.longitude, "timezone": "auto", "forecast_days": 7,
                "current": "temperature_2m,apparent_temperature,weather_code",
                "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
                "temperature_unit": "fahrenheit" if fahrenheit else "celsius",
            })).json()
        return describe(place.name, data, offset)

    @staticmethod
    def _fail(reason: str) -> Dict[str, Any]:
        return {"action": "weather", "success": False, "verified": False, "error": reason}


def describe(place: str, data: Dict[str, Any], offset: int = 0) -> Dict[str, Any]:
    """Forecast JSON -> a short sentence plus the numbers used."""
    daily = data["daily"]
    day = {
        "date": daily["time"][offset],
        "condition": _CONDITIONS.get(daily["weather_code"][offset], "mixed weather"),
        "high": round(daily["temperature_2m_max"][offset]),
        "low": round(daily["temperature_2m_min"][offset]),
        "rain_chance": daily["precipitation_probability_max"][offset],
    }
    rain = f", {day['rain_chance']}% chance of rain" if day["rain_chance"] is not None else ""
    if offset == 0:
        current = data["current"]
        now = round(current["temperature_2m"])
        feels = round(current["apparent_temperature"])
        condition = _CONDITIONS.get(current["weather_code"], "mixed weather")
        feels_text = f", feels like {feels}°" if abs(feels - now) >= 3 else ""
        summary = (f"It's {now}° and {condition} in {place}{feels_text}. "
                   f"Today: high {day['high']}°, low {day['low']}°{rain}.")
        day.update(now=now, feels_like=feels, now_condition=condition)
    else:
        when = "Tomorrow" if offset == 1 else datetime.fromisoformat(day["date"]).strftime("%A")
        summary = f"{when} in {place}: {day['condition']}, high {day['high']}°, low {day['low']}°{rain}."
    day.update(place=place, summary=summary)
    return day


weather_tool = WeatherTool()
tool_registry.register_tool(weather_tool)
