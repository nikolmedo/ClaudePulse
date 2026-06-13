"""Tests for the Claude Pulse config, options, and reauth flows."""
from __future__ import annotations

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.claude_pulse.api import ClaudeApiError, ClaudeAuthError
from custom_components.claude_pulse.const import DOMAIN

from .conftest import MOCK_CONFIG

VALIDATE = "custom_components.claude_pulse.config_flow.ClaudeApiClient.async_validate"


async def test_user_flow_success(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(VALIDATE, return_value=None):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_CONFIG
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "ClaudePulse"
    assert result["data"] == MOCK_CONFIG


async def test_user_flow_invalid_auth(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(VALIDATE, side_effect=ClaudeAuthError("HTTP 401")):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_CONFIG
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_user_flow_cannot_connect(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(VALIDATE, side_effect=ClaudeApiError("HTTP 500")):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_CONFIG
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_aborts_on_duplicate_org(hass: HomeAssistant) -> None:
    MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, unique_id=MOCK_CONFIG["org_id"]
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_CONFIG
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_flow_updates_session_key(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, unique_id=MOCK_CONFIG["org_id"]
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth"

    with patch(VALIDATE, return_value=None):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"session_key": "new-key"}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data["session_key"] == "new-key"
    assert entry.data["org_id"] == MOCK_CONFIG["org_id"]


async def test_reauth_flow_rejects_bad_key(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, unique_id=MOCK_CONFIG["org_id"]
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    with patch(VALIDATE, side_effect=ClaudeAuthError("HTTP 401")):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"session_key": "still-bad"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}
    assert entry.data["session_key"] == MOCK_CONFIG["session_key"]


async def test_options_flow_updates_entry(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, unique_id=MOCK_CONFIG["org_id"]
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM

    new_input = {**MOCK_CONFIG, "update_interval": 300}
    with patch(VALIDATE, return_value=None):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input=new_input
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.data["update_interval"] == 300
