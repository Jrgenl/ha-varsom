"""Base entity for Varsom."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, CONF_MUNICIPALITY_NAME, DOMAIN
from .coordinator import VarsomCoordinator


class VarsomEntity(CoordinatorEntity[VarsomCoordinator]):
    """An entity belonging to one Varsom location."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(self, coordinator: VarsomCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_translation_key = key
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"Varsom {entry.data[CONF_MUNICIPALITY_NAME]}",
            manufacturer="NVE",
            model="Varsom",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://www.varsom.no/",
        )
