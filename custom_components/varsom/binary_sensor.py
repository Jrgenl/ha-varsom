"""Binary sensors that turn on when a warning is in force."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .api import Warning
from .const import WARNING_THRESHOLDS
from .coordinator import VarsomConfigEntry, VarsomCoordinator
from .entity import VarsomEntity
from .sensor import level_name


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VarsomConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Varsom binary sensors."""
    coordinator = entry.runtime_data
    entities: list[BinarySensorEntity] = [
        VarsomWarningBinarySensor(coordinator, warning_type)
        for warning_type in coordinator.warning_types
    ]
    entities.append(VarsomAnyWarningBinarySensor(coordinator))
    async_add_entities(entities)


def _active_warnings(coordinator: VarsomCoordinator) -> list[Warning]:
    """Return current warnings at or above the threshold for their type."""
    now = dt_util.now()
    active: list[Warning] = []
    for warning_type, forecast in coordinator.data.items():
        warning = forecast.current(now)
        if warning and warning.level >= WARNING_THRESHOLDS[warning_type]:
            active.append(warning)
    return active


class VarsomWarningBinarySensor(VarsomEntity, BinarySensorEntity):
    """On when the current warning for one type is at or above its threshold."""

    _attr_device_class = BinarySensorDeviceClass.SAFETY

    def __init__(self, coordinator: VarsomCoordinator, warning_type: str) -> None:
        super().__init__(coordinator, f"{warning_type}_warning")
        self._warning_type = warning_type

    @property
    def _warning(self) -> Warning | None:
        forecast = self.coordinator.data.get(self._warning_type)
        return forecast.current(dt_util.now()) if forecast else None

    @property
    def available(self) -> bool:
        return super().available and self._warning is not None

    @property
    def is_on(self) -> bool | None:
        warning = self._warning
        if warning is None:
            return None
        return warning.level >= WARNING_THRESHOLDS[self._warning_type]

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        warning = self._warning
        if warning is None:
            return None
        return {
            "level": warning.level,
            "level_name": level_name(warning.warning_type, warning.level),
            "threshold": WARNING_THRESHOLDS[self._warning_type],
        }


class VarsomAnyWarningBinarySensor(VarsomEntity, BinarySensorEntity):
    """On when any enabled warning type has an active warning."""

    _attr_device_class = BinarySensorDeviceClass.SAFETY

    def __init__(self, coordinator: VarsomCoordinator) -> None:
        super().__init__(coordinator, "any_warning")

    @property
    def is_on(self) -> bool:
        return bool(_active_warnings(self.coordinator))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "active_warnings": [
                {
                    "type": warning.warning_type,
                    "level": warning.level,
                    "level_name": level_name(warning.warning_type, warning.level),
                    "main_text": warning.main_text,
                }
                for warning in _active_warnings(self.coordinator)
            ]
        }
