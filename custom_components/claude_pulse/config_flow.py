"""Config flow for Claude Pulse — handles UI-driven setup, options, and re-authentication."""
from __future__ import annotations

import logging

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api import ClaudeApiClient, ClaudeApiError, ClaudeAuthError
from .const import (
    CONF_FABLE_QUOTA,
    CONF_NAME,
    CONF_ORG_ID,
    CONF_SESSION_KEY,
    CONF_UPDATE_INTERVAL,
    DEFAULT_FABLE_QUOTA,
    DEFAULT_NAME,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    MIN_UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
        vol.Required(CONF_SESSION_KEY): str,
        vol.Required(CONF_ORG_ID): str,
        vol.Optional(CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL): vol.All(
            int, vol.Range(min=MIN_UPDATE_INTERVAL)
        ),
        vol.Optional(CONF_FABLE_QUOTA, default=DEFAULT_FABLE_QUOTA): bool,
    }
)

STEP_REAUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SESSION_KEY): str,
    }
)


async def _test_credentials(hass, session_key: str, org_id: str) -> str | None:
    """Make a live request to verify credentials.

    Returns None on success, or an error key string that maps to strings.json.
    """
    # Use a throwaway session without a cookie jar so the check really uses
    # the entered session key and cannot pick up cookies of another account
    # from Home Assistant's shared session.
    session = async_create_clientsession(
        hass, auto_cleanup=False, cookie_jar=aiohttp.DummyCookieJar()
    )
    client = ClaudeApiClient(
        session=session,
        session_key=session_key,
        org_id=org_id,
    )
    try:
        await client.async_validate()
    except ClaudeAuthError:
        return "invalid_auth"
    except ClaudeApiError:
        return "cannot_connect"
    finally:
        # The connector is shared with HA, so detach instead of close.
        session.detach()
    return None


class ClaudePulseConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the Claude Pulse setup flow."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> ClaudePulseOptionsFlow:
        """Return the options flow handler."""
        return ClaudePulseOptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Show the setup form and validate credentials."""
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_ORG_ID])
            self._abort_if_unique_id_configured()

            error_key = await _test_credentials(
                self.hass,
                user_input[CONF_SESSION_KEY],
                user_input[CONF_ORG_ID],
            )
            if error_key is None:
                data = dict(user_input)
                title = data.pop(CONF_NAME, "").strip() or DEFAULT_NAME
                return self.async_create_entry(title=title, data=data)
            errors["base"] = error_key

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
            description_placeholders={"claude_url": "claude.ai"},
        )

    async def async_step_reauth(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Re-authentication step triggered by ConfigEntryAuthFailed."""
        errors: dict[str, str] = {}

        if user_input is not None:
            org_id = self._get_reauth_entry().data.get(CONF_ORG_ID, "")
            error_key = await _test_credentials(
                self.hass, user_input[CONF_SESSION_KEY], org_id
            )
            if error_key is None:
                self.hass.config_entries.async_update_entry(
                    self._get_reauth_entry(),
                    data={
                        **self._get_reauth_entry().data,
                        CONF_SESSION_KEY: user_input[CONF_SESSION_KEY],
                    },
                )
                await self.hass.config_entries.async_reload(
                    self._get_reauth_entry().entry_id
                )
                return self.async_abort(reason="reauth_successful")
            errors["base"] = error_key

        return self.async_show_form(
            step_id="reauth",
            data_schema=STEP_REAUTH_SCHEMA,
            errors=errors,
            description_placeholders={"claude_url": "claude.ai"},
        )


class ClaudePulseOptionsFlow(config_entries.OptionsFlow):
    """Handle Claude Pulse options — edit session key, org ID, and update interval."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._entry = config_entry

    async def async_step_init(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Show the options form pre-filled with current values."""
        errors: dict[str, str] = {}
        current = self._entry.data

        if user_input is not None:
            new_org_id = user_input[CONF_ORG_ID]
            if new_org_id != self._entry.unique_id and any(
                other.unique_id == new_org_id
                for other in self.hass.config_entries.async_entries(DOMAIN)
                if other.entry_id != self._entry.entry_id
            ):
                errors["base"] = "already_configured"
            else:
                error_key = await _test_credentials(
                    self.hass, user_input[CONF_SESSION_KEY], new_org_id
                )
                if error_key is None:
                    # Keep the unique_id in sync with the org ID. (The old
                    # code called a non-existent async_set_unique_id here.)
                    self.hass.config_entries.async_update_entry(
                        self._entry,
                        data={**current, **user_input},
                        unique_id=new_org_id,
                    )
                    await self.hass.config_entries.async_reload(
                        self._entry.entry_id
                    )
                    return self.async_create_entry(title="", data={})
                errors["base"] = error_key

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SESSION_KEY,
                    description={"suggested_value": current.get(CONF_SESSION_KEY, "")},
                ): str,
                vol.Required(
                    CONF_ORG_ID,
                    description={"suggested_value": current.get(CONF_ORG_ID, "")},
                ): str,
                vol.Optional(
                    CONF_UPDATE_INTERVAL,
                    description={
                        "suggested_value": current.get(
                            CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
                        )
                    },
                ): vol.All(int, vol.Range(min=MIN_UPDATE_INTERVAL)),
                vol.Optional(
                    CONF_FABLE_QUOTA,
                    description={
                        "suggested_value": current.get(
                            CONF_FABLE_QUOTA, DEFAULT_FABLE_QUOTA
                        )
                    },
                ): bool,
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
            description_placeholders={"claude_url": "claude.ai"},
        )
