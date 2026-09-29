"""Sensors with the current and next warning level for each warning type."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .api import Warning
from .const import TYPE_AVALANCHE, VARSOM_URLS
from .coordinator import VarsomConfigEntry, VarsomCoordinator
from .entity import VarsomEntity

FLOOD_LANDSLIDE_LEVELS = {1: "green", 2: "yellow", 3: "orange", 4: "red"}
AVALANCHE_LEVELS = {
    0: "not_assessed",
    1: "low",
    2: "moderate",
    3: "considerable",
    4: "high",
    5: "very_high",
}


def level_name(warning_type: str, level: int) -> str | None:
    """Return a stable, language independent name for a level."""
    if warning_type == TYPE_AVALANCHE:
        return AVALANCHE_LEVELS.get(level)
    return FLOOD_LANDSLIDE_LEVELS.get(level)


def warning_attributes(warning: Warning) -> dict[str, Any]:
    """Build state attributes for a warning."""
    attributes: dict[str, Any] = {
        "level_name": level_name(warning.warning_type, warning.level),
        "valid_from": warning.valid_from.isoformat(),
        "valid_to": warning.valid_to.isoformat(),
        "main_text": warning.main_text,
        "warning_text": warning.warning_text,
        "advice": warning.advice_text,
        "consequence": warning.consequence_text,
        "danger_type": warning.danger_type,
        "causes": list(warning.causes),
        "region": warning.region_name,
        "published": warning.published.isoformat() if warning.published else None,
        "danger_increase": (
            warning.danger_increase.isoformat() if warning.danger_increase else None
        ),
        "danger_decrease": (
            warning.danger_decrease.isoformat() if warning.danger_decrease else None
        ),
        "url": VARSOM_URLS[warning.warning_type],
    }
    return {key: value for key, value in attributes.items() if value not in (None, [])}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VarsomConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Varsom sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        VarsomLevelSensor(coordinator, warning_type, upcoming)
        for warning_type in coordinator.warning_types
        for upcoming in (False, True)
    )


class VarsomLevelSensor(VarsomEntity, SensorEntity):
    """Warning level for the current or the next forecast period."""

    _unrecorded_attributes = frozenset(
        {"main_text", "warning_text", "advice", "consequence", "causes", "url"}
    )

    def __init__(
        self, coordinator: VarsomCoordinator, warning_type: str, upcoming: bool
    ) -> None:
        super().__init__(
            coordinator, f"{warning_type}_{'tomorrow' if upcoming else 'today'}"
        )
        self._warning_type = warning_type
        self._upcoming = upcoming

    @property
    def _warning(self) -> Warning | None:
        forecast = self.coordinator.data.get(self._warning_type)
        if forecast is None:
            return None
        now = dt_util.now()
        return forecast.upcoming(now) if self._upcoming else forecast.current(now)

    @property
    def available(self) -> bool:
        return super().available and self._warning is not None

    @property
    def native_value(self) -> int | None:
        warning = self._warning
        return warning.level if warning else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        warning = self._warning
        return warning_attributes(warning) if warning else None
