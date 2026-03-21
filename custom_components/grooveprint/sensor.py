"""Sensor entity for Grooveprint."""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import GrooveprintCoordinator

ICON_MAP = {
    "idle": "mdi:sleep",
    "listening": "mdi:ear-hearing",
    "playing": "mdi:music-circle",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Grooveprint sensor from a config entry."""
    coordinator: GrooveprintCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([GrooveprintStatusSensor(coordinator, entry)])


class GrooveprintStatusSensor(
    CoordinatorEntity[GrooveprintCoordinator], SensorEntity
):
    """Sensor showing the raw Grooveprint server status."""

    _attr_has_entity_name = True
    _attr_name = "Status"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["idle", "listening", "playing"]

    def __init__(
        self, coordinator: GrooveprintCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_status"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Grooveprint",
            manufacturer="Grooveprint",
        )

    @property
    def available(self) -> bool:
        """Return True if the server is reachable."""
        return self.coordinator.data.get("server_available", False)

    @property
    def native_value(self) -> str | None:
        """Return the current status."""
        return self.coordinator.data.get("status")

    @property
    def icon(self) -> str:
        """Return icon based on status."""
        status = self.coordinator.data.get("status", "idle")
        return ICON_MAP.get(status, "mdi:sleep")
