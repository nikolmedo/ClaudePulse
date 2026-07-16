"""Tests for integration setup, sensors, and unload."""
from __future__ import annotations

from unittest.mock import patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.claude_pulse.api import ClaudeApiError, ClaudeAuthError
from custom_components.claude_pulse.const import DOMAIN

from .conftest import MOCK_CONFIG, MOCK_ORG, MOCK_PAYLOAD

GET_USAGE = "custom_components.claude_pulse.api.ClaudeApiClient.async_get_usage"
GET_ORG = (
    "custom_components.claude_pulse.api.ClaudeApiClient.async_get_organization"
)


async def _setup_entry(
    hass: HomeAssistant,
    data: dict | None = None,
    org: dict | Exception = MOCK_ORG,
) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN, data=data or MOCK_CONFIG, unique_id=MOCK_CONFIG["org_id"]
    )
    entry.add_to_hass(hass)
    org_kwargs = (
        {"side_effect": org} if isinstance(org, Exception) else {"return_value": org}
    )
    with patch(GET_USAGE, return_value=MOCK_PAYLOAD), patch(GET_ORG, **org_kwargs):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


async def test_setup_creates_all_sensors(hass: HomeAssistant) -> None:
    entry = await _setup_entry(hass)
    assert entry.state is ConfigEntryState.LOADED

    registry = er.async_get(hass)
    expected_keys = (
        "session_pct",
        "weekly_pct",
        "session_countdown",
        "session_reset_time",
        "weekly_reset",
        "weekly_reset_weekday",
        "weekly_reset_time",
        "session_used",
        "session_limit",
        "plan",
    )
    for key in expected_keys:
        entity_id = registry.async_get_entity_id(
            "sensor", DOMAIN, f"{entry.entry_id}_{key}"
        )
        assert entity_id is not None, f"missing sensor for {key}"


async def test_fable_sensors_created_by_default(hass: HomeAssistant) -> None:
    entry = await _setup_entry(hass)
    registry = er.async_get(hass)
    for key in ("fable_pct", "fable_reset"):
        entity_id = registry.async_get_entity_id(
            "sensor", DOMAIN, f"{entry.entry_id}_{key}"
        )
        assert entity_id is not None, f"missing sensor for {key}"


async def test_fable_sensors_omitted_when_disabled(hass: HomeAssistant) -> None:
    entry = await _setup_entry(hass, data={**MOCK_CONFIG, "fable_quota": False})
    registry = er.async_get(hass)
    for key in ("fable_pct", "fable_reset"):
        entity_id = registry.async_get_entity_id(
            "sensor", DOMAIN, f"{entry.entry_id}_{key}"
        )
        assert entity_id is None, f"unexpected sensor for {key}"
    # Non-fable sensors are still present.
    assert (
        registry.async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_session_pct")
        is not None
    )


async def test_sensor_values(hass: HomeAssistant) -> None:
    entry = await _setup_entry(hass)
    registry = er.async_get(hass)

    def state_of(key: str):
        entity_id = registry.async_get_entity_id(
            "sensor", DOMAIN, f"{entry.entry_id}_{key}"
        )
        return hass.states.get(entity_id)

    assert state_of("session_pct").state == "22.0"
    assert state_of("weekly_pct").state == "41.0"
    assert state_of("session_limit").state == "100.0"
    assert state_of("plan").state == "Max 5x"
    assert state_of("weekly_reset").state != "N/A"


async def test_org_fetch_failure_is_non_fatal(hass: HomeAssistant) -> None:
    entry = await _setup_entry(hass, org=ClaudeApiError("org endpoint down"))
    assert entry.state is ConfigEntryState.LOADED

    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_plan"
    )
    assert hass.states.get(entity_id).state == "N/A"


async def test_unload_entry(hass: HomeAssistant) -> None:
    entry = await _setup_entry(hass)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert entry.entry_id not in hass.data.get(DOMAIN, {})


async def test_auth_failure_starts_reauth(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, unique_id=MOCK_CONFIG["org_id"]
    )
    entry.add_to_hass(hass)
    with patch(GET_USAGE, side_effect=ClaudeAuthError("HTTP 401")):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert any(flow["context"]["source"] == "reauth" for flow in flows)


async def test_network_failure_retries(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, unique_id=MOCK_CONFIG["org_id"]
    )
    entry.add_to_hass(hass)
    with patch(GET_USAGE, side_effect=ClaudeApiError("all endpoints failed")):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
