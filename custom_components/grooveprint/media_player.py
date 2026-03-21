"""Media player entity for Grooveprint."""
from __future__ import annotations

from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerState,
    MediaType,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.dt import utcnow

from .const import CONF_SERVER_URL, DOMAIN
from .coordinator import GrooveprintCoordinator

STATE_MAP = {
    "playing": MediaPlayerState.PLAYING,
    "listening": MediaPlayerState.IDLE,
    "idle": MediaPlayerState.STANDBY,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Grooveprint media player from a config entry."""
    coordinator: GrooveprintCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([GrooveprintMediaPlayer(coordinator, entry)])


class GrooveprintMediaPlayer(
    CoordinatorEntity[GrooveprintCoordinator], MediaPlayerEntity
):
    """Representation of the Grooveprint now-playing state."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_media_content_type = MediaType.MUSIC
    _attr_supported_features = 0

    def __init__(
        self, coordinator: GrooveprintCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize the media player."""
        super().__init__(coordinator)
        self._server_url = entry.data[CONF_SERVER_URL]
        self._attr_unique_id = f"{entry.entry_id}_media_player"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Grooveprint",
            manufacturer="Grooveprint",
        )
        self._position_updated_at = None

    @property
    def available(self) -> bool:
        """Return True if the server is reachable."""
        return self.coordinator.data.get("server_available", False)

    @property
    def state(self) -> MediaPlayerState | None:
        """Return the current state."""
        status = self.coordinator.data.get("status", "idle")
        return STATE_MAP.get(status, MediaPlayerState.STANDBY)

    @property
    def media_title(self) -> str | None:
        """Return the title of the current track."""
        return self.coordinator.data.get("track")

    @property
    def media_artist(self) -> str | None:
        """Return the artist of the current track."""
        return self.coordinator.data.get("artist")

    @property
    def media_album_name(self) -> str | None:
        """Return the album name."""
        return self.coordinator.data.get("album")

    @property
    def media_duration(self) -> float | None:
        """Return the duration in seconds."""
        return self.coordinator.data.get("duration_s")

    @property
    def media_position(self) -> float | None:
        """Return the current playback position in seconds."""
        return self.coordinator.data.get("elapsed_s")

    @property
    def media_position_updated_at(self):
        """Return when the position was last updated."""
        return self._position_updated_at

    @property
    def media_image_url(self) -> str | None:
        """Return the cover art URL."""
        cover_url = self.coordinator.data.get("cover_url")
        if cover_url:
            return f"{self._server_url}{cover_url}"
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes for automations."""
        data = self.coordinator.data
        attrs = {}
        for key in ("side", "position", "track_number", "year", "score", "confidence", "discogs_url"):
            val = data.get(key)
            if val is not None:
                attrs[key] = val
        return attrs

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.data.get("elapsed_s") is not None:
            self._position_updated_at = utcnow()
        super()._handle_coordinator_update()
