"""Tests for the Varsom API client and parsing."""

from __future__ import annotations

from datetime import date, datetime

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import pytest

from custom_components.varsom.api import (
    AVALANCHE_URL,
    FLOOD_URL,
    KARTVERKET_URL,
    LANDSLIDE_URL,
    Forecast,
    VarsomApiClient,
    VarsomConnectionError,
    VarsomOutsideNorwayError,
    parse_avalanche,
    parse_flood_landslide,
)
from custom_components.varsom.const import NVE_TIMEZONE

from .conftest import load_fixture


def oslo(*args: int) -> datetime:
    return datetime(*args, tzinfo=NVE_TIMEZONE)


def test_parse_landslide() -> None:
    warnings = parse_flood_landslide("landslide", load_fixture("landslide.json"))

    assert [w.level for w in warnings] == [3, 2, 1]
    first = warnings[0]
    assert first.valid_from == oslo(2026, 9, 19, 7)
    assert first.danger_type == "Jord- og flomskredfare"
    assert first.causes == ("Regn", "Intens regn (bygenedbør)")
    assert first.advice_text.startswith("Hold deg unna bratte skråninger")
    assert first.published is not None
    # Offsets in the payload are kept, naive times get Europe/Oslo.
    assert first.danger_decrease == oslo(2026, 9, 20, 7)


def test_parse_avalanche() -> None:
    warnings = parse_avalanche(load_fixture("avalanche.json"))

    assert len(warnings) == 3
    assert warnings[0].level == 2
    assert warnings[0].region_name == "Tromsø"
    assert warnings[0].region_type == "A"
    assert parse_avalanche(None) == []


def test_parse_skips_invalid_items() -> None:
    assert parse_flood_landslide("flood", [{"ActivityLevel": "2"}]) == []
    warnings = parse_flood_landslide(
        "flood",
        [
            {
                "ActivityLevel": None,
                "ValidFrom": "2026-09-19T07:00:00",
                "ValidTo": "2026-09-20T06:59:59",
            }
        ],
    )
    assert warnings[0].level == 0


@pytest.mark.parametrize(
    ("now", "current", "upcoming"),
    [
        # Before the first period has started.
        (oslo(2026, 9, 19, 6), None, 3),
        (oslo(2026, 9, 19, 7), 3, 2),
        (oslo(2026, 9, 20, 6, 30), 3, 2),
        (oslo(2026, 9, 20, 12), 2, 1),
        (oslo(2026, 9, 22, 6, 59, 30), 1, None),
        # Expired data is never reported as current.
        (oslo(2026, 9, 23, 12), None, None),
    ],
)
def test_forecast_periods(
    now: datetime, current: int | None, upcoming: int | None
) -> None:
    forecast = Forecast(
        "landslide", parse_flood_landslide("landslide", load_fixture("landslide.json"))
    )

    assert (w.level if (w := forecast.current(now)) else None) == current
    assert (w.level if (w := forecast.upcoming(now)) else None) == upcoming


def test_forecast_uses_most_severe_warning_per_period() -> None:
    warnings = parse_flood_landslide("flood", load_fixture("flood.json"))
    severe = parse_flood_landslide("landslide", load_fixture("landslide.json"))[0]
    mixed = Forecast("flood", [warnings[0], severe])

    assert mixed.current(oslo(2026, 9, 19, 12)).level == 3


async def test_client_requests(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.get(KARTVERKET_URL, json=load_fixture("kommuneinfo.json"))
    aioclient_mock.get(
        f"{FLOOD_URL}/4601/1/2026-09-19/2026-09-21", json=load_fixture("flood.json")
    )
    aioclient_mock.get(
        f"{LANDSLIDE_URL}/4601/1/2026-09-19/2026-09-21",
        json=load_fixture("landslide.json"),
    )
    aioclient_mock.get(
        f"{AVALANCHE_URL}/69.65/18.95/1/2026-03-01/2026-03-03",
        json=load_fixture("avalanche.json"),
    )
    client = VarsomApiClient(async_get_clientsession(hass))

    location = await client.async_get_location(60.39, 5.32)
    assert location.municipality_id == "4601"
    assert location.municipality_name == "Bergen"
    assert location.county_name == "Vestland"

    start, end = date(2026, 9, 19), date(2026, 9, 21)
    assert len(await client.async_get_flood("4601", 1, start, end)) == 3
    assert len(await client.async_get_landslide("4601", 1, start, end)) == 3
    avalanche = await client.async_get_avalanche(
        69.65, 18.95, 1, date(2026, 3, 1), date(2026, 3, 3)
    )
    assert avalanche[0].region_id == 3011


async def test_location_outside_norway(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.get(KARTVERKET_URL, status=404)
    client = VarsomApiClient(async_get_clientsession(hass))

    with pytest.raises(VarsomOutsideNorwayError):
        await client.async_get_location(55.6, 12.5)


async def test_server_error(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.get(KARTVERKET_URL, status=500)
    client = VarsomApiClient(async_get_clientsession(hass))

    with pytest.raises(VarsomConnectionError):
        await client.async_get_location(60.39, 5.32)
