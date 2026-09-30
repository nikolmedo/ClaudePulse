"""Regression tests: several accounts must never share credentials.

Before the fix, every entry used Home Assistant's shared aiohttp session.
Its global cookie jar stored the ``sessionKey`` cookie set by claude.ai,
and aiohttp let that jar cookie override the manually set Cookie header —
so with two entries, both ended up querying whichever account answered last.
"""
from __future__ import annotations

from collections.abc import AsyncGenerator
from unittest.mock import patch

from aiohttp import ThreadedResolver, web
import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.claude_pulse.const import DOMAIN

from .conftest import MOCK_CONFIG, MOCK_CONFIG_B

KEY_TO_PCT = {
    MOCK_CONFIG["session_key"]: 11,
    MOCK_CONFIG_B["session_key"]: 77,
}


@pytest.fixture
async def os_resolver() -> AsyncGenerator[None]:
    """Resolve hostnames through the OS instead of the harness's aiodns mock.

    pytest-homeassistant-custom-component replaces HA's DNS resolver with an
    aiodns ``AsyncResolver`` that fails here with "'NoneType' object has no
    attribute 'getaddrinfo'", so "localhost" would never resolve.
    """
    resolver = ThreadedResolver()
    # HA's connector teardown calls ``real_close`` on the mocked resolver.
    resolver.real_close = resolver.close
    with patch(
        "homeassistant.helpers.aiohttp_client._async_make_resolver",
        return_value=resolver,
    ):
        yield


async def _fake_claude(aiohttp_server):
    """A tiny claude.ai stand-in that answers per session key and sets cookies."""

    async def usage(request: web.Request) -> web.Response:
        key = request.cookies.get("sessionKey")
        if key not in KEY_TO_PCT:
            return web.Response(status=403)
        resp = web.json_response(
            {
                "five_hour": {"utilization": KEY_TO_PCT[key], "resets_at": None},
                "seven_day": {"utilization": KEY_TO_PCT[key], "resets_at": None},
            }
        )
        # claude.ai refreshes the session cookie — this is what poisoned the
        # shared jar before the fix.
        resp.set_cookie("sessionKey", key)
        return resp

    async def org(request: web.Request) -> web.Response:
        return web.json_response({"capabilities": ["claude_pro"]})

    app = web.Application()
    app.router.add_get("/api/organizations/{org}/usage", usage)
    app.router.add_get("/api/organizations/{org}", org)
    return await aiohttp_server(app)


async def test_two_accounts_keep_their_own_data(
    hass: HomeAssistant, aiohttp_server, monkeypatch, socket_enabled, os_resolver
) -> None:
    server = await _fake_claude(aiohttp_server)
    # Point the client at the fake server. Use "localhost" (a hostname) so a
    # real cookie jar would accept the cookie and the old bug would reproduce.
    monkeypatch.setattr(
        "custom_components.claude_pulse.api.CLAUDE_BASE_URL",
        f"http://localhost:{server.port}",
    )

    entry_a = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, unique_id=MOCK_CONFIG["org_id"],
        title="Private",
    )
    entry_b = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG_B, unique_id=MOCK_CONFIG_B["org_id"],
        title="Work",
    )
    entry_a.add_to_hass(hass)
    entry_b.add_to_hass(hass)

    # Setting up the domain loads every entry of it.
    assert await hass.config_entries.async_setup(entry_a.entry_id)
    await hass.async_block_till_done()

    coord_a = hass.data[DOMAIN][entry_a.entry_id]
    coord_b = hass.data[DOMAIN][entry_b.entry_id]

    # Refresh alternately a few times — with the shared jar, B would start
    # reporting A's numbers (or fail auth) after A's response set the cookie.
    for coord in (coord_a, coord_b, coord_a, coord_b):
        await coord.async_refresh()

    assert coord_a.last_update_success
    assert coord_b.last_update_success
    assert coord_a.data["session_pct"] == 11
    assert coord_b.data["session_pct"] == 77

    # Each account gets its own, distinguishable device and entities.
    devices = dr.async_get(hass)
    names = {
        devices.async_get_device(identifiers={(DOMAIN, e.entry_id)}).name
        for e in (entry_a, entry_b)
    }
    assert names == {"Private", "Work"}

    registry = er.async_get(hass)
    id_a = registry.async_get_entity_id("sensor", DOMAIN, f"{entry_a.entry_id}_session_pct")
    id_b = registry.async_get_entity_id("sensor", DOMAIN, f"{entry_b.entry_id}_session_pct")
    assert id_a != id_b
    assert float(hass.states.get(id_a).state) == 11
    assert float(hass.states.get(id_b).state) == 77


async def test_legacy_entry_keeps_original_device_name(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, unique_id=MOCK_CONFIG["org_id"],
        title="ClaudePulse",
    )
    entry.add_to_hass(hass)
    with patch(
        "custom_components.claude_pulse.api.ClaudeApiClient.async_get_usage",
        return_value={"five_hour": {"utilization": 1}, "seven_day": {"utilization": 1}},
    ), patch(
        "custom_components.claude_pulse.api.ClaudeApiClient.async_get_organization",
        return_value={},
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, entry.entry_id)})
    assert device.name == "Claude Pulse"
