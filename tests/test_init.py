"""Tests for setting up Varsom and its entities."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.varsom.api import (
    VarsomConnectionError,
    parse_avalanche,
    parse_flood_landslide,
)
from custom_components.varsom.const import (
    CONF_COUNTY_NAME,
    CONF_MUNICIPALITY_ID,
    CONF_MUNICIPALITY_NAME,
    CONF_WARNING_TYPES,
    DOMAIN,
)

from .conftest import load_fixture

CLIENT = "custom_components.varsom.coordinator.VarsomApiClient"


@pytest.fixture
def entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Bergen",
        unique_id="60.39_5.32",
        data={
            CONF_LATITUDE: 60.39,
            CONF_LONGITUDE: 5.32,
            CONF_MUNICIPALITY_ID: "4601",
            CONF_MUNICIPALITY_NAME: "Bergen",
            CONF_COUNTY_NAME: "Vestland",
        },
        options={CONF_WARNING_TYPES: ["flood", "landslide", "avalanche"]},
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def mock_client():
    with patch(CLIENT, autospec=True) as client_cls:
        client = client_cls.return_value
        client.async_get_flood = AsyncMock(
            return_value=parse_flood_landslide("flood", load_fixture("flood.json"))
        )
        client.async_get_landslide = AsyncMock(
            return_value=parse_flood_landslide(
                "landslide", load_fixture("landslide.json")
            )
        )
        client.async_get_avalanche = AsyncMock(
            return_value=parse_avalanche(load_fixture("avalanche.json"))
        )
        yield client


@pytest.mark.freeze_time("2026-09-19 10:00:00+00:00")
async def test_entities(hass: HomeAssistant, entry, mock_client) -> None:
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    today = hass.states.get("sensor.varsom_bergen_landslide_level_today")
    assert today.state == "3"
    assert today.attributes["level_name"] == "orange"
    assert today.attributes["danger_type"] == "Jord- og flomskredfare"
    assert today.attributes["attribution"].startswith("Data fra Varsom.no")

    tomorrow = hass.states.get("sensor.varsom_bergen_landslide_level_tomorrow")
    assert tomorrow.state == "2"
    assert tomorrow.attributes["level_name"] == "yellow"

    assert hass.states.get("sensor.varsom_bergen_flood_level_today").state == "1"
    assert (
        hass.states.get("binary_sensor.varsom_bergen_flood_warning").state == STATE_OFF
    )
    assert (
        hass.states.get("binary_sensor.varsom_bergen_landslide_warning").state
        == STATE_ON
    )

    # The avalanche fixture is from March, so nothing is valid today.
    assert (
        hass.states.get("sensor.varsom_bergen_avalanche_danger_today").state
        == STATE_UNAVAILABLE
    )

    any_warning = hass.states.get("binary_sensor.varsom_bergen_warning")
    assert any_warning.state == STATE_ON
    assert [w["type"] for w in any_warning.attributes["active_warnings"]] == [
        "landslide"
    ]

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_only_enabled_types_are_fetched(
    hass: HomeAssistant, entry, mock_client
) -> None:
    hass.config_entries.async_update_entry(
        entry, options={CONF_WARNING_TYPES: ["flood"]}
    )
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    mock_client.async_get_flood.assert_awaited_once()
    mock_client.async_get_landslide.assert_not_awaited()
    mock_client.async_get_avalanche.assert_not_awaited()
    assert hass.states.get("sensor.varsom_bergen_landslide_level_today") is None


async def test_setup_retry_on_error(hass: HomeAssistant, entry, mock_client) -> None:
    mock_client.async_get_flood.side_effect = VarsomConnectionError("boom")
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
