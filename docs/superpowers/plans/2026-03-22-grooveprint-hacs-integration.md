# Grooveprint HACS Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a HACS custom integration that exposes a Grooveprint vinyl fingerprinting server and its companion listening app as Home Assistant entities.

**Architecture:** Single coordinator with SSE push from the Grooveprint server and periodic polling of the listening app. Three entities: media_player (track info), sensor (status), switch (start/stop listening). Config flow for setup.

**Tech Stack:** Python, Home Assistant custom component APIs, aiohttp (bundled with HA)

**Spec:** `docs/superpowers/specs/2026-03-22-grooveprint-hacs-integration-design.md`

---

### Task 1: Project scaffolding — const.py, manifest.json, hacs.json, strings.json

**Files:**
- Create: `custom_components/grooveprint/const.py`
- Create: `custom_components/grooveprint/manifest.json`
- Create: `custom_components/grooveprint/strings.json`
- Create: `custom_components/grooveprint/translations/en.json`
- Create: `hacs.json`

- [ ] **Step 1: Create `const.py`**

```python
"""Constants for the Grooveprint integration."""

DOMAIN = "grooveprint"

CONF_SERVER_URL = "server_url"
CONF_LISTENER_URL = "listener_url"

DEFAULT_SERVER_URL = "http://localhost:8457"
DEFAULT_LISTENER_URL = "http://localhost:8458"

PLATFORMS = ["media_player", "sensor", "switch"]

RECONNECT_INTERVAL = 5  # seconds
LISTENER_POLL_INTERVAL = 5  # seconds
SSE_HEARTBEAT_TIMEOUT = 60  # seconds
```

- [ ] **Step 2: Create `manifest.json`**

```json
{
  "domain": "grooveprint",
  "name": "Grooveprint",
  "codeowners": [],
  "config_flow": true,
  "documentation": "https://github.com/leolobato/grooveprint-hass",
  "integration_type": "hub",
  "iot_class": "local_push",
  "issue_tracker": "https://github.com/leolobato/grooveprint-hass/issues",
  "requirements": [],
  "version": "1.0.0"
}
```

- [ ] **Step 3: Create `strings.json`**

```json
{
  "config": {
    "step": {
      "user": {
        "title": "Connect to Grooveprint",
        "description": "Enter the URLs of your Grooveprint server and listening app.",
        "data": {
          "server_url": "Server URL",
          "listener_url": "Listening app URL"
        }
      }
    },
    "error": {
      "cannot_connect_server": "Cannot connect to Grooveprint server.",
      "cannot_connect_listener": "Cannot connect to listening app.",
      "unknown": "Unexpected error occurred."
    },
    "abort": {
      "already_configured": "This server is already configured."
    }
  }
}
```

- [ ] **Step 4: Create `translations/en.json`**

Same content as `strings.json`.

- [ ] **Step 5: Create `hacs.json`**

```json
{
  "name": "Grooveprint",
  "homeassistant": "2024.1.0",
  "render_readme": true
}
```

- [ ] **Step 6: Commit**

```bash
git add custom_components/grooveprint/const.py custom_components/grooveprint/manifest.json custom_components/grooveprint/strings.json custom_components/grooveprint/translations/en.json hacs.json
git commit -m "feat: add project scaffolding"
```

---

### Task 2: Config flow

**Files:**
- Create: `custom_components/grooveprint/config_flow.py`

- [ ] **Step 1: Create `config_flow.py`**

```python
"""Config flow for Grooveprint integration."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_LISTENER_URL,
    CONF_SERVER_URL,
    DEFAULT_LISTENER_URL,
    DEFAULT_SERVER_URL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SERVER_URL, default=DEFAULT_SERVER_URL): str,
        vol.Required(CONF_LISTENER_URL, default=DEFAULT_LISTENER_URL): str,
    }
)


class GrooveprintConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Grooveprint."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            server_url = user_input[CONF_SERVER_URL].rstrip("/")
            listener_url = user_input[CONF_LISTENER_URL].rstrip("/")

            # Check for duplicate
            await self.async_set_unique_id(server_url)
            self._abort_if_unique_id_configured()

            session = async_get_clientsession(self.hass)

            # Validate server
            try:
                async with session.get(
                    f"{server_url}/health", timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status != 200:
                        errors["base"] = "cannot_connect_server"
            except (aiohttp.ClientError, TimeoutError):
                errors["base"] = "cannot_connect_server"
            except Exception:
                _LOGGER.exception("Unexpected error validating server")
                errors["base"] = "unknown"

            # Validate listener
            if not errors:
                try:
                    async with session.get(
                        f"{listener_url}/status",
                        timeout=aiohttp.ClientTimeout(total=10),
                    ) as resp:
                        if resp.status != 200:
                            errors["base"] = "cannot_connect_listener"
                except (aiohttp.ClientError, TimeoutError):
                    errors["base"] = "cannot_connect_listener"
                except Exception:
                    _LOGGER.exception("Unexpected error validating listener")
                    errors["base"] = "unknown"

            if not errors:
                return self.async_create_entry(
                    title="Grooveprint",
                    data={
                        CONF_SERVER_URL: server_url,
                        CONF_LISTENER_URL: listener_url,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
```

- [ ] **Step 2: Commit**

```bash
git add custom_components/grooveprint/config_flow.py
git commit -m "feat: add config flow with dual URL validation"
```

---

### Task 3: Coordinator

This is the core of the integration — SSE connection to the server and polling of the listening app.

**Files:**
- Create: `custom_components/grooveprint/coordinator.py`

- [ ] **Step 1: Create `coordinator.py`**

```python
"""DataUpdateCoordinator for Grooveprint."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_LISTENER_URL,
    CONF_SERVER_URL,
    DOMAIN,
    LISTENER_POLL_INTERVAL,
    RECONNECT_INTERVAL,
    SSE_HEARTBEAT_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)


class GrooveprintCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to manage SSE connection and listener polling."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=None,
        )
        self.entry = entry
        self.server_url: str = entry.data[CONF_SERVER_URL]
        self.listener_url: str = entry.data[CONF_LISTENER_URL]
        self._sse_task: asyncio.Task | None = None
        self._listener_task: asyncio.Task | None = None
        self._server_available = False
        self._listener_available = False
        self._is_listening = False
        self._now_playing: dict[str, Any] = {"status": "idle"}

    async def async_start(self) -> None:
        """Start SSE and listener polling tasks."""
        self._sse_task = asyncio.create_task(self._sse_loop())
        self._listener_task = asyncio.create_task(self._listener_poll_loop())

    async def async_stop(self) -> None:
        """Stop background tasks."""
        for task in (self._sse_task, self._listener_task):
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch current state from server for initial refresh."""
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(
                f"{self.server_url}/now-playing",
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 200:
                    self._now_playing = await resp.json()
                    self._server_available = True
        except (aiohttp.ClientError, asyncio.TimeoutError):
            self._server_available = False
        return self._build_data()

    def _build_data(self) -> dict[str, Any]:
        """Build the data dict from current state."""
        data = dict(self._now_playing)
        data["is_listening"] = self._is_listening
        data["listener_available"] = self._listener_available
        data["server_available"] = self._server_available
        return data

    def _push_update(self) -> None:
        """Push updated data to all entities."""
        self.async_set_updated_data(self._build_data())

    # --- SSE connection ---

    async def _sse_loop(self) -> None:
        """Main SSE loop with reconnection."""
        session = async_get_clientsession(self.hass)

        while True:
            try:
                await self._connect_and_listen(session)
            except (aiohttp.ClientError, asyncio.TimeoutError) as err:
                _LOGGER.warning("SSE connection failed: %s", err)
                self._server_available = False
                self._push_update()
            except asyncio.CancelledError:
                break

            _LOGGER.info("SSE reconnecting in %s seconds...", RECONNECT_INTERVAL)
            await asyncio.sleep(RECONNECT_INTERVAL)

    async def _connect_and_listen(self, session: aiohttp.ClientSession) -> None:
        """Connect to SSE stream and listen for events."""
        url = f"{self.server_url}/now-playing/stream"
        _LOGGER.info("Connecting to SSE: %s", url)

        async with session.get(
            url, timeout=aiohttp.ClientTimeout(total=None)
        ) as resp:
            if resp.status != 200:
                raise aiohttp.ClientError(f"SSE returned {resp.status}")

            self._server_available = True
            _LOGGER.info("SSE connected")

            while True:
                try:
                    async with asyncio.timeout(SSE_HEARTBEAT_TIMEOUT):
                        line_bytes = await resp.content.readline()
                except TimeoutError:
                    _LOGGER.warning("SSE heartbeat timeout, reconnecting")
                    return

                if not line_bytes:
                    break  # stream ended

                line = line_bytes.decode("utf-8").strip()

                # Skip empty lines and heartbeat comments
                if not line or line.startswith(":"):
                    continue

                if line.startswith("data:"):
                    json_str = line[5:].strip()
                    try:
                        self._now_playing = json.loads(json_str)
                        self._push_update()
                    except json.JSONDecodeError:
                        _LOGGER.warning("Failed to parse SSE data: %s", json_str)

    # --- Listener polling ---

    async def _listener_poll_loop(self) -> None:
        """Poll the listening app for status."""
        session = async_get_clientsession(self.hass)

        while True:
            try:
                async with session.get(
                    f"{self.listener_url}/status",
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        self._is_listening = data.get("state") in (
                            "listening",
                            "matched",
                        )
                        self._listener_available = True
                    else:
                        self._listener_available = False
            except (aiohttp.ClientError, asyncio.TimeoutError):
                self._listener_available = False
            except asyncio.CancelledError:
                break

            self._push_update()

            try:
                await asyncio.sleep(LISTENER_POLL_INTERVAL)
            except asyncio.CancelledError:
                break

    # --- Listener commands ---

    async def async_start_listening(self) -> None:
        """Send start command to listening app."""
        session = async_get_clientsession(self.hass)
        try:
            async with session.post(
                f"{self.listener_url}/start",
                timeout=aiohttp.ClientTimeout(total=5),
            ):
                pass
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            _LOGGER.error("Failed to start listening: %s", err)

    async def async_stop_listening(self) -> None:
        """Send stop command to listening app."""
        session = async_get_clientsession(self.hass)
        try:
            async with session.post(
                f"{self.listener_url}/stop",
                timeout=aiohttp.ClientTimeout(total=5),
            ):
                pass
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            _LOGGER.error("Failed to stop listening: %s", err)
```

- [ ] **Step 2: Commit**

```bash
git add custom_components/grooveprint/coordinator.py
git commit -m "feat: add coordinator with SSE and listener polling"
```

---

### Task 4: Media player entity

**Files:**
- Create: `custom_components/grooveprint/media_player.py`

- [ ] **Step 1: Create `media_player.py`**

```python
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
```

- [ ] **Step 2: Commit**

```bash
git add custom_components/grooveprint/media_player.py
git commit -m "feat: add media player entity with track info"
```

---

### Task 5: Sensor entity

**Files:**
- Create: `custom_components/grooveprint/sensor.py`

- [ ] **Step 1: Create `sensor.py`**

```python
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
```

- [ ] **Step 2: Commit**

```bash
git add custom_components/grooveprint/sensor.py
git commit -m "feat: add status sensor entity"
```

---

### Task 6: Switch entity

**Files:**
- Create: `custom_components/grooveprint/switch.py`

- [ ] **Step 1: Create `switch.py`**

```python
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
```

- [ ] **Step 2: Commit**

```bash
git add custom_components/grooveprint/switch.py
git commit -m "feat: add listening switch entity"
```

---

### Task 7: Integration setup — __init__.py

**Files:**
- Create: `custom_components/grooveprint/__init__.py`

- [ ] **Step 1: Create `__init__.py`**

```python
"""The Grooveprint integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS
from .coordinator import GrooveprintCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Grooveprint from a config entry."""
    coordinator = GrooveprintCoordinator(hass, entry)

    await coordinator.async_start()
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    coordinator: GrooveprintCoordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_stop()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
```

- [ ] **Step 2: Commit**

```bash
git add custom_components/grooveprint/__init__.py
git commit -m "feat: add integration setup and teardown"
```

---

### Task 8: Manual integration test

Verify everything works end-to-end against the real Grooveprint server.

- [ ] **Step 1: Copy `custom_components/grooveprint/` to HA custom_components directory**

Either symlink or copy into your Home Assistant config directory:
```bash
ln -s /path/to/grooveprint-hass/custom_components/grooveprint /path/to/ha-config/custom_components/grooveprint
```

- [ ] **Step 2: Restart Home Assistant and add the integration**

Go to Settings → Integrations → Add Integration → search "Grooveprint". Enter the server URL and listening app URL. Verify the config flow validates both endpoints.

- [ ] **Step 3: Verify entities appear**

Check that three entities are created under the "Grooveprint" device:
- `media_player.grooveprint`
- `sensor.grooveprint_status`
- `switch.grooveprint_listening`

- [ ] **Step 4: Test status sensor**

With the server idle, verify `sensor.grooveprint_status` shows `idle`. Start listening and play a record — verify it transitions through `listening` → `playing`.

- [ ] **Step 5: Test media player**

While a track is playing, verify:
- State is `playing`
- Track title, artist, album are populated
- Cover art loads
- Duration and position are shown
- Extra attributes (side, track_number, etc.) are present in developer tools

- [ ] **Step 6: Test listening switch**

Toggle `switch.grooveprint_listening` on and off. Verify:
- Switch state reflects the listening app's actual state
- Turning on sends `/start` to the listening app
- Turning off sends `/stop` to the listening app

- [ ] **Step 7: Test error handling**

- Stop the Grooveprint server → media_player and sensor should become `unavailable`
- Restart the server → entities should recover automatically
- Close the listening app → switch should become `unavailable`
- Reopen the app → switch should recover

- [ ] **Step 8: Final commit**

```bash
git commit --allow-empty -m "feat: integration verified end-to-end"
```
