"""Client for the NVE (Varsom) warning APIs and Kartverket municipality lookup."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

import aiohttp

from .const import NVE_TIMEZONE, TYPE_AVALANCHE, TYPE_FLOOD, TYPE_LANDSLIDE

KARTVERKET_URL = "https://api.kartverket.no/kommuneinfo/v1/punkt"
NVE_BASE_URL = "https://api01.nve.no/hydrology/forecast"
FLOOD_URL = f"{NVE_BASE_URL}/flood/v1.0.10/api/Warning/Municipality"
LANDSLIDE_URL = f"{NVE_BASE_URL}/landslide/v1.0.10/api/Warning/Municipality"
AVALANCHE_URL = (
    f"{NVE_BASE_URL}/avalanche/v6.3.0/api/AvalancheWarningByCoordinates/Simple"
)

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)
HEADERS = {"Accept": "application/json"}
PERIOD_GRACE = timedelta(minutes=5)


class VarsomError(Exception):
    """Base error for the Varsom client."""


class VarsomConnectionError(VarsomError):
    """Raised when an API cannot be reached or returns an error."""


class VarsomOutsideNorwayError(VarsomError):
    """Raised when a location is not inside a Norwegian municipality."""


@dataclass(frozen=True)
class Location:
    """A Norwegian municipality resolved from coordinates."""

    municipality_id: str
    municipality_name: str
    county_name: str | None


@dataclass(frozen=True)
class Warning:
    """A single warning from Varsom, normalised across warning types."""

    warning_type: str
    level: int
    valid_from: datetime
    valid_to: datetime
    main_text: str | None = None
    warning_text: str | None = None
    advice_text: str | None = None
    consequence_text: str | None = None
    danger_type: str | None = None
    causes: tuple[str, ...] = ()
    region_id: int | None = None
    region_name: str | None = None
    region_type: str | None = None
    published: datetime | None = None
    danger_increase: datetime | None = None
    danger_decrease: datetime | None = None


@dataclass
class Forecast:
    """Warnings for one warning type, split into the current and next period."""

    warning_type: str
    warnings: list[Warning] = field(default_factory=list)

    def _periods(self) -> list[Warning]:
        """Return the most severe warning for each validity period, sorted."""
        periods: dict[datetime, Warning] = {}
        for warning in self.warnings:
            existing = periods.get(warning.valid_from)
            if existing is None or warning.level > existing.level:
                periods[warning.valid_from] = warning
        return [periods[key] for key in sorted(periods)]

    def current(self, now: datetime) -> Warning | None:
        """Return the warning for the period in force now.

        NVE ends some periods at 06:59:00 and others at 06:59:59, so a short
        grace period bridges the gap to the next one.
        """
        active = [
            w
            for w in self._periods()
            if w.valid_from <= now < w.valid_to + PERIOD_GRACE
        ]
        return active[-1] if active else None

    def upcoming(self, now: datetime) -> Warning | None:
        """Return the warning for the next period that has not started yet."""
        return next((w for w in self._periods() if w.valid_from > now), None)


def _parse_datetime(value: Any) -> datetime | None:
    """Parse an NVE timestamp, assuming Norwegian local time if no offset."""
    if not value or not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=NVE_TIMEZONE)
    return parsed


def _parse_level(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _clean_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def parse_flood_landslide(
    warning_type: str, data: list[dict[str, Any]]
) -> list[Warning]:
    """Parse the response from the flood or landslide API."""
    warnings: list[Warning] = []
    for item in data:
        valid_from = _parse_datetime(item.get("ValidFrom"))
        valid_to = _parse_datetime(item.get("ValidTo"))
        if valid_from is None or valid_to is None:
            continue
        warnings.append(
            Warning(
                warning_type=warning_type,
                level=_parse_level(item.get("ActivityLevel")),
                valid_from=valid_from,
                valid_to=valid_to,
                main_text=_clean_text(item.get("MainText")),
                warning_text=_clean_text(item.get("WarningText")),
                advice_text=_clean_text(item.get("AdviceText")),
                consequence_text=_clean_text(item.get("ConsequenceText")),
                danger_type=_clean_text(item.get("DangerTypeName")),
                causes=tuple(
                    cause["Name"]
                    for cause in item.get("CauseList") or []
                    if isinstance(cause, dict) and cause.get("Name")
                ),
                published=_parse_datetime(item.get("PublishTime")),
                danger_increase=_parse_datetime(item.get("DangerIncreaseDateTime")),
                danger_decrease=_parse_datetime(item.get("DangerDecreaseDateTime")),
            )
        )
    return warnings


def parse_avalanche(data: list[dict[str, Any]] | None) -> list[Warning]:
    """Parse the response from the avalanche API."""
    warnings: list[Warning] = []
    for item in data or []:
        valid_from = _parse_datetime(item.get("ValidFrom"))
        valid_to = _parse_datetime(item.get("ValidTo"))
        if valid_from is None or valid_to is None:
            continue
        warnings.append(
            Warning(
                warning_type=TYPE_AVALANCHE,
                level=_parse_level(item.get("DangerLevel")),
                valid_from=valid_from,
                valid_to=valid_to,
                main_text=_clean_text(item.get("MainText")),
                region_id=item.get("RegionId"),
                region_name=_clean_text(item.get("RegionName")),
                region_type=_clean_text(item.get("RegionTypeName")),
                published=_parse_datetime(item.get("PublishTime")),
                danger_increase=_parse_datetime(item.get("DangerIncreaseTime")),
                danger_decrease=_parse_datetime(item.get("DangerDecreaseTime")),
            )
        )
    return warnings


class VarsomApiClient:
    """Async client for the Varsom warning APIs."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session

    async def _get_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        try:
            async with self._session.get(
                url, params=params, headers=HEADERS, timeout=REQUEST_TIMEOUT
            ) as response:
                if response.status == 404:
                    return None
                response.raise_for_status()
                return await response.json(content_type=None)
        except (TimeoutError, aiohttp.ClientError, ValueError) as err:
            raise VarsomConnectionError(f"Error fetching {url}: {err}") from err

    async def async_get_location(self, latitude: float, longitude: float) -> Location:
        """Resolve coordinates to a Norwegian municipality using Kartverket."""
        data = await self._get_json(
            KARTVERKET_URL,
            {"nord": latitude, "ost": longitude, "koordsys": 4258},
        )
        if not data or not data.get("kommunenummer"):
            raise VarsomOutsideNorwayError(
                f"No Norwegian municipality at {latitude}, {longitude}"
            )
        return Location(
            municipality_id=data["kommunenummer"],
            municipality_name=data.get("kommunenavn") or data["kommunenummer"],
            county_name=data.get("fylkesnavn"),
        )

    async def async_get_flood(
        self, municipality_id: str, lang: int, start: date, end: date
    ) -> list[Warning]:
        """Fetch flood warnings for a municipality."""
        data = await self._get_json(
            f"{FLOOD_URL}/{municipality_id}/{lang}/{start.isoformat()}/{end.isoformat()}"
        )
        return parse_flood_landslide(TYPE_FLOOD, data or [])

    async def async_get_landslide(
        self, municipality_id: str, lang: int, start: date, end: date
    ) -> list[Warning]:
        """Fetch landslide warnings for a municipality."""
        data = await self._get_json(
            f"{LANDSLIDE_URL}/{municipality_id}/{lang}/{start.isoformat()}/{end.isoformat()}"
        )
        return parse_flood_landslide(TYPE_LANDSLIDE, data or [])

    async def async_get_avalanche(
        self, latitude: float, longitude: float, lang: int, start: date, end: date
    ) -> list[Warning]:
        """Fetch avalanche warnings for the region containing the coordinates."""
        data = await self._get_json(
            f"{AVALANCHE_URL}/{latitude}/{longitude}/{lang}/{start.isoformat()}/{end.isoformat()}"
        )
        return parse_avalanche(data)
