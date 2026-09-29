"""Config flow for Varsom."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_LATITUDE, CONF_LOCATION, CONF_LONGITUDE
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    LocationSelector,
    LocationSelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.util import dt as dt_util
import voluptuous as vol

from .api import VarsomApiClient, VarsomConnectionError, VarsomOutsideNorwayError
from .const import (
    CONF_AVALANCHE_REGION_ID,
    CONF_AVALANCHE_REGION_NAME,
    CONF_COUNTY_NAME,
    CONF_MUNICIPALITY_ID,
    CONF_MUNICIPALITY_NAME,
    CONF_WARNING_TYPES,
    DOMAIN,
    LANG_NORWEGIAN,
    NVE_TIMEZONE,
    TYPE_FLOOD,
    TYPE_LANDSLIDE,
    WARNING_TYPES,
)

_LOGGER = logging.getLogger(__name__)


def _warning_types_schema(default: list[str]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_WARNING_TYPES, default=default): SelectSelector(
                SelectSelectorConfig(
                    options=list(WARNING_TYPES),
                    multiple=True,
                    mode=SelectSelectorMode.LIST,
                    translation_key=CONF_WARNING_TYPES,
                )
            )
        }
    )


class VarsomConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Varsom."""

    VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._default_types: list[str] = [TYPE_FLOOD, TYPE_LANDSLIDE]

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the location to monitor."""
        errors: dict[str, str] = {}

        if user_input is not None:
            latitude = round(float(user_input[CONF_LOCATION][CONF_LATITUDE]), 4)
            longitude = round(float(user_input[CONF_LOCATION][CONF_LONGITUDE]), 4)

            await self.async_set_unique_id(f"{latitude}_{longitude}")
            self._abort_if_unique_id_configured()

            client = VarsomApiClient(async_get_clientsession(self.hass))
            try:
                location = await client.async_get_location(latitude, longitude)
                today = dt_util.now(NVE_TIMEZONE).date()
                avalanche = await client.async_get_avalanche(
                    latitude,
                    longitude,
                    LANG_NORWEGIAN,
                    today,
                    today + timedelta(days=1),
                )
            except VarsomOutsideNorwayError:
                errors["base"] = "outside_norway"
            except VarsomConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error while setting up Varsom")
                errors["base"] = "unknown"
            else:
                self._data = {
                    CONF_LATITUDE: latitude,
                    CONF_LONGITUDE: longitude,
                    CONF_MUNICIPALITY_ID: location.municipality_id,
                    CONF_MUNICIPALITY_NAME: location.municipality_name,
                    CONF_COUNTY_NAME: location.county_name,
                }
                if avalanche:
                    self._data[CONF_AVALANCHE_REGION_ID] = avalanche[0].region_id
                    self._data[CONF_AVALANCHE_REGION_NAME] = avalanche[0].region_name
                    # Only "A" regions get daily avalanche forecasts.
                    if avalanche[0].region_type == "A":
                        self._default_types = list(WARNING_TYPES)
                return await self.async_step_warning_types()

        home = {
            CONF_LATITUDE: self.hass.config.latitude,
            CONF_LONGITUDE: self.hass.config.longitude,
        }
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_LOCATION, default=home): LocationSelector(
                        LocationSelectorConfig(radius=False)
                    )
                }
            ),
            errors=errors,
        )

    async def async_step_warning_types(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose which warning types to monitor."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if not user_input[CONF_WARNING_TYPES]:
                errors["base"] = "no_warning_types"
            else:
                return self.async_create_entry(
                    title=self._data[CONF_MUNICIPALITY_NAME],
                    data=self._data,
                    options={CONF_WARNING_TYPES: user_input[CONF_WARNING_TYPES]},
                )

        return self.async_show_form(
            step_id="warning_types",
            data_schema=_warning_types_schema(self._default_types),
            description_placeholders={
                "municipality": self._data[CONF_MUNICIPALITY_NAME],
                "avalanche_region": self._data.get(CONF_AVALANCHE_REGION_NAME) or "-",
            },
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> VarsomOptionsFlow:
        """Return the options flow."""
        return VarsomOptionsFlow()


class VarsomOptionsFlow(OptionsFlow):
    """Change which warning types are monitored."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            if not user_input[CONF_WARNING_TYPES]:
                errors["base"] = "no_warning_types"
            else:
                return self.async_create_entry(data=user_input)

        current = self.config_entry.options.get(CONF_WARNING_TYPES, list(WARNING_TYPES))
        return self.async_show_form(
            step_id="init",
            data_schema=_warning_types_schema(current),
            errors=errors,
        )
