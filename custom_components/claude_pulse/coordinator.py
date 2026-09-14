"""DataUpdateCoordinator for Claude Pulse.

Framework layer — adapts the domain (models) and infrastructure (api) to
Home Assistant. Fetching and parsing live in api.py / models.py.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

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

# The subscription plan changes rarely, so the organization payload is
# refreshed far less often than the usage data. Failed fetches are retried
# sooner so a transient error at startup does not stick for hours.
ORG_REFRESH_INTERVAL = timedelta(hours=6)
ORG_RETRY_INTERVAL = timedelta(minutes=15)


class ClaudePulseCoordinator(DataUpdateCoordinator):
    """Fetches Claude usage data from claude.ai on a configurable interval."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.client = ClaudeApiClient(
            session=async_get_clientsession(hass),
            session_key=entry.data[CONF_SESSION_KEY],
            org_id=entry.data.get(CONF_ORG_ID, ""),
        )
        self._org: dict | None = None
        self._org_expires: datetime | None = None
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

        org = await self._async_get_organization()
        return ClaudeUsage.from_payload(raw, org=org).as_sensor_data()

    async def _async_get_organization(self) -> dict | None:
        """Return the cached organization payload, refreshing when stale.

        Failures are non-fatal: the usage fetch above is the authority on
        auth and connectivity, so a broken org call only means the plan
        sensor keeps its last known value (or "N/A").
        """
        now = datetime.now(tz=timezone.utc)
        if self._org_expires and now < self._org_expires:
            return self._org
        try:
            self._org = await self.client.async_get_organization()
            self._org_expires = now + ORG_REFRESH_INTERVAL
        except ClaudeApiError as err:
            self._org_expires = now + ORG_RETRY_INTERVAL
            _LOGGER.debug("Organization fetch failed, plan unchanged: %s", err)
        return self._org
