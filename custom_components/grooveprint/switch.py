"""Switch entity for Grooveprint."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import GrooveprintCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Grooveprint switch from a config entry."""
    coordinator: GrooveprintCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([GrooveprintListeningSwitch(coordinator, entry)])


class GrooveprintListeningSwitch(
    CoordinatorEntity[GrooveprintCoordinator], SwitchEntity
):
    """Switch to control the Grooveprint listening app."""

    _attr_has_entity_name = True
    _attr_name = "Listening"

    def __init__(
        self, coordinator: GrooveprintCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_listening"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Grooveprint",
            manufacturer="Grooveprint",
        )

    @property
    def available(self) -> bool:
        """Return True if the listening app is reachable."""
        return self.coordinator.data.get("listener_available", False)

    @property
    def is_on(self) -> bool:
        """Return True if listening."""
        return self.coordinator.data.get("is_listening", False)

    @property
    def icon(self) -> str:
        """Return icon based on state."""
        return "mdi:microphone" if self.is_on else "mdi:microphone-off"

    async def async_turn_on(self, **kwargs) -> None:
        """Start listening."""
        await self.coordinator.async_start_listening()

    async def async_turn_off(self, **kwargs) -> None:
        """Stop listening."""
        await self.coordinator.async_stop_listening()
