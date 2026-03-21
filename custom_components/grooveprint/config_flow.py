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
