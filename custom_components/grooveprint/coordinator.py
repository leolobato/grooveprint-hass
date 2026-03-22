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
                else:
                    _LOGGER.warning("GET /now-playing returned %s", resp.status)
                    self._server_available = False
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
            ) as resp:
                _LOGGER.debug("Start listening response: %s", resp.status)
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            _LOGGER.error("Failed to start listening: %s", err)

    async def async_stop_listening(self) -> None:
        """Send stop command to listening app."""
        session = async_get_clientsession(self.hass)
        try:
            async with session.post(
                f"{self.listener_url}/stop",
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                _LOGGER.debug("Stop listening response: %s", resp.status)
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            _LOGGER.error("Failed to stop listening: %s", err)
