"""Unit tests for the API client (api.py) — aiohttp mocked, no Home Assistant."""
from __future__ import annotations

import aiohttp
import pytest
from aioresponses import aioresponses

from custom_components.claude_pulse.api import (
    ClaudeApiClient,
    ClaudeApiError,
    ClaudeAuthError,
)

from .conftest import MOCK_PAYLOAD

ORG_ID = "11111111-2222-3333-4444-555555555555"
ORG_URL = f"https://claude.ai/api/organizations/{ORG_ID}/usage"
USAGE_URL = "https://claude.ai/api/usage"
ACCOUNT_URL = "https://claude.ai/api/account/usage"


@pytest.fixture
async def session():
    async with aiohttp.ClientSession() as client_session:
        yield client_session


async def test_org_endpoint_success(session):
    client = ClaudeApiClient(session, "test-key", ORG_ID)
    with aioresponses() as mocked:
        mocked.get(ORG_URL, payload=MOCK_PAYLOAD)
        assert await client.async_get_usage() == MOCK_PAYLOAD


async def test_fallback_to_usage_endpoint(session):
    client = ClaudeApiClient(session, "test-key", ORG_ID)
    with aioresponses() as mocked:
        mocked.get(ORG_URL, status=404)
        mocked.get(USAGE_URL, payload=MOCK_PAYLOAD)
        assert await client.async_get_usage() == MOCK_PAYLOAD


async def test_fallback_to_account_endpoint(session):
    client = ClaudeApiClient(session, "test-key", ORG_ID)
    with aioresponses() as mocked:
        mocked.get(ORG_URL, status=500)
        mocked.get(USAGE_URL, status=404)
        mocked.get(ACCOUNT_URL, payload=MOCK_PAYLOAD)
        assert await client.async_get_usage() == MOCK_PAYLOAD


async def test_no_org_id_skips_org_endpoint(session):
    client = ClaudeApiClient(session, "test-key")
    with aioresponses() as mocked:
        mocked.get(USAGE_URL, payload=MOCK_PAYLOAD)
        assert await client.async_get_usage() == MOCK_PAYLOAD


async def test_401_raises_auth_error(session):
    client = ClaudeApiClient(session, "expired-key", ORG_ID)
    with aioresponses() as mocked:
        mocked.get(ORG_URL, status=401)
        with pytest.raises(ClaudeAuthError):
            await client.async_get_usage()


async def test_403_on_fallback_raises_auth_error(session):
    client = ClaudeApiClient(session, "expired-key", ORG_ID)
    with aioresponses() as mocked:
        mocked.get(ORG_URL, status=404)
        mocked.get(USAGE_URL, status=403)
        with pytest.raises(ClaudeAuthError):
            await client.async_get_usage()


async def test_all_endpoints_fail_raises_api_error(session):
    client = ClaudeApiClient(session, "test-key", ORG_ID)
    with aioresponses() as mocked:
        mocked.get(ORG_URL, status=500)
        mocked.get(USAGE_URL, status=404)
        mocked.get(ACCOUNT_URL, status=503)
        with pytest.raises(ClaudeApiError, match="All Claude.ai endpoints failed"):
            await client.async_get_usage()


async def test_network_error_falls_through(session):
    client = ClaudeApiClient(session, "test-key", ORG_ID)
    with aioresponses() as mocked:
        mocked.get(ORG_URL, exception=aiohttp.ClientConnectionError("boom"))
        mocked.get(USAGE_URL, payload=MOCK_PAYLOAD)
        assert await client.async_get_usage() == MOCK_PAYLOAD


async def test_session_key_sent_as_cookie(session):
    client = ClaudeApiClient(session, "my-secret", ORG_ID)
    with aioresponses() as mocked:
        mocked.get(ORG_URL, payload=MOCK_PAYLOAD)
        await client.async_get_usage()
        request = list(mocked.requests.values())[0][0]
        assert request.kwargs["headers"]["Cookie"] == "sessionKey=my-secret"


async def test_validate_success(session):
    client = ClaudeApiClient(session, "test-key", ORG_ID)
    with aioresponses() as mocked:
        mocked.get(ORG_URL, payload=MOCK_PAYLOAD)
        await client.async_validate()  # must not raise


async def test_validate_auth_error(session):
    client = ClaudeApiClient(session, "expired-key", ORG_ID)
    with aioresponses() as mocked:
        mocked.get(ORG_URL, status=403)
        with pytest.raises(ClaudeAuthError):
            await client.async_validate()


async def test_validate_http_error(session):
    client = ClaudeApiClient(session, "test-key", ORG_ID)
    with aioresponses() as mocked:
        mocked.get(ORG_URL, status=500)
        with pytest.raises(ClaudeApiError):
            await client.async_validate()


async def test_validate_network_error(session):
    client = ClaudeApiClient(session, "test-key", ORG_ID)
    with aioresponses() as mocked:
        mocked.get(ORG_URL, exception=aiohttp.ClientConnectionError("boom"))
        with pytest.raises(ClaudeApiError):
            await client.async_validate()
