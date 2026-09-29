"""Tests for the Varsom config and options flows."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_LATITUDE, CONF_LOCATION, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.varsom.api import (
    Location,
    VarsomConnectionError,
    VarsomOutsideNorwayError,
    parse_avalanche,
)
from custom_components.varsom.const import (
    CONF_MUNICIPALITY_ID,
    CONF_WARNING_TYPES,
    DOMAIN,
)

from .conftest import load_fixture

BERGEN = {CONF_LOCATION: {CONF_LATITUDE: 60.39, CONF_LONGITUDE: 5.32}}
TROMSO = {CONF_LOCATION: {CONF_LATITUDE: 69.65, CONF_LONGITUDE: 18.95}}


@pytest.fixture
def mock_client():
    with patch(
        "custom_components.varsom.config_flow.VarsomApiClient", autospec=True
    ) as client_cls:
        client = client_cls.return_value
        client.async_get_location = AsyncMock(
            return_value=Location("4601", "Bergen", "Vestland")
        )
        client.async_get_avalanche = AsyncMock(return_value=[])
        yield client


@pytest.fixture(autouse=True)
def mock_setup_entry():
    with patch(
        "custom_components.varsom.async_setup_entry", return_value=True
    ) as setup_entry:
        yield setup_entry


async def test_user_flow(hass: HomeAssistant, mock_client) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], BERGEN)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "warning_types"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_WARNING_TYPES: ["flood", "landslide"]}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Bergen"
    assert result["data"][CONF_MUNICIPALITY_ID] == "4601"
    assert result["data"][CONF_LATITUDE] == 60.39
    assert result["options"] == {CONF_WARNING_TYPES: ["flood", "landslide"]}
    assert result["result"].unique_id == "60.39_5.32"


async def test_avalanche_enabled_by_default_in_forecast_region(
    hass: HomeAssistant, mock_client
) -> None:
    mock_client.async_get_avalanche.return_value = parse_avalanche(
        load_fixture("avalanche.json")
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], TROMSO)

    schema = result["data_schema"].schema
    default = next(iter(schema)).default()
    assert default == ["flood", "landslide", "avalanche"]
    assert result["description_placeholders"]["avalanche_region"] == "Tromsø"


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (VarsomOutsideNorwayError, "outside_norway"),
        (VarsomConnectionError, "cannot_connect"),
        (RuntimeError, "unknown"),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant, mock_client, error: type[Exception], expected: str
) -> None:
    mock_client.async_get_location.side_effect = error
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], BERGEN)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected}

    # The flow recovers once the error is gone.
    mock_client.async_get_location.side_effect = None
    result = await hass.config_entries.flow.async_configure(result["flow_id"], BERGEN)
    assert result["step_id"] == "warning_types"


async def test_no_warning_types(hass: HomeAssistant, mock_client) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], BERGEN)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_WARNING_TYPES: []}
    )
    assert result["errors"] == {"base": "no_warning_types"}


async def test_already_configured(hass: HomeAssistant, mock_client) -> None:
    MockConfigEntry(domain=DOMAIN, unique_id="60.39_5.32").add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], BERGEN)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, options={CONF_WARNING_TYPES: ["flood"]})
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_WARNING_TYPES: []}
    )
    assert result["errors"] == {"base": "no_warning_types"}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_WARNING_TYPES: ["flood", "avalanche"]}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {CONF_WARNING_TYPES: ["flood", "avalanche"]}
