"""DataUpdateCoordinator for Claude Pulse.

Framework layer — adapts the domain (models) and infrastructure (api) to
Home Assistant. Fetching and parsing live in api.py / models.py.
"""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ClaudeApiClient, ClaudeApiError, ClaudeAuthError
from .const import (
    CONF_ORG_ID,
    CONF_SESSION_KEY,
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
)
from .models import ClaudeUsage

_LOGGER = logging.getLogger(__name__)


class ClaudePulseCoordinator(DataUpdateCoordinator):
    """Fetches Claude usage data from claude.ai on a configurable interval."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.client = ClaudeApiClient(
            session=async_get_clientsession(hass),
            session_key=entry.data[CONF_SESSION_KEY],
            org_id=entry.data.get(CONF_ORG_ID, ""),
        )
        interval = entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=interval),
        )

    async def _async_update_data(self) -> dict:
        """Fetch latest usage data from claude.ai.

        Raises:
            ConfigEntryAuthFailed: On HTTP 401/403 — triggers HA reauth flow.
            UpdateFailed: On all other errors.
        """
        try:
            raw = await self.client.async_get_usage()
        except ClaudeAuthError as err:
            raise ConfigEntryAuthFailed(
                f"{err} Please update your session key."
            ) from err
        except ClaudeApiError as err:
            raise UpdateFailed(str(err)) from err

        return ClaudeUsage.from_payload(raw).as_sensor_data()
