"""Shared fixtures for Claude Pulse tests."""
from __future__ import annotations

import pytest

MOCK_PAYLOAD = {
    "five_hour": {"utilization": 22, "resets_at": "2026-06-10T18:00:00Z"},
    "seven_day": {"utilization": 41, "resets_at": "2026-06-12T03:45:00Z"},
}

MOCK_CONFIG = {
    "session_key": "sk-ant-sid01-test-key",
    "org_id": "11111111-2222-3333-4444-555555555555",
    "update_interval": 120,
}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable loading custom integrations in all tests."""
    yield
