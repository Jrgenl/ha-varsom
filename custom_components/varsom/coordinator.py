"""Data update coordinator for Varsom."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import Forecast, VarsomApiClient, VarsomError
from .const import (
    CONF_MUNICIPALITY_ID,
    CONF_WARNING_TYPES,
    DOMAIN,
    LANG_ENGLISH,
    LANG_NORWEGIAN,
    NVE_TIMEZONE,
    TYPE_AVALANCHE,
    TYPE_FLOOD,
    TYPE_LANDSLIDE,
    UPDATE_INTERVAL,
    WARNING_TYPES,
)

_LOGGER = logging.getLogger(__name__)

type VarsomConfigEntry = ConfigEntry[VarsomCoordinator]


def enabled_warning_types(entry: ConfigEntry) -> list[str]:
    """Return the warning types enabled for an entry."""
    return list(entry.options.get(CONF_WARNING_TYPES, WARNING_TYPES))


class VarsomCoordinator(DataUpdateCoordinator[dict[str, Forecast]]):
    """Fetch all enabled warning types for one location."""

    config_entry: VarsomConfigEntry

    def __init__(self, hass: HomeAssistant, entry: VarsomConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.client = VarsomApiClient(async_get_clientsession(hass))
        self.warning_types = enabled_warning_types(entry)
        language = (hass.config.language or "").lower()
        self.lang = LANG_NORWEGIAN if language in ("nb", "nn", "no") else LANG_ENGLISH

    async def _async_update_data(self) -> dict[str, Forecast]:
        data = self.config_entry.data
        # Flood and landslide periods run 07:00-07:00, so before 07:00 the
        # period in force started yesterday.
        start = dt_util.now(NVE_TIMEZONE).date() - timedelta(days=1)
        end = start + timedelta(days=3)

        requests = {}
        if TYPE_FLOOD in self.warning_types:
            requests[TYPE_FLOOD] = self.client.async_get_flood(
                data[CONF_MUNICIPALITY_ID], self.lang, start, end
            )
        if TYPE_LANDSLIDE in self.warning_types:
            requests[TYPE_LANDSLIDE] = self.client.async_get_landslide(
                data[CONF_MUNICIPALITY_ID], self.lang, start, end
            )
        if TYPE_AVALANCHE in self.warning_types:
            requests[TYPE_AVALANCHE] = self.client.async_get_avalanche(
                data[CONF_LATITUDE], data[CONF_LONGITUDE], self.lang, start, end
            )

        try:
            results = await asyncio.gather(*requests.values())
        except VarsomError as err:
            raise UpdateFailed(str(err)) from err

        return {
            warning_type: Forecast(warning_type, warnings)
            for warning_type, warnings in zip(requests, results, strict=True)
        }
