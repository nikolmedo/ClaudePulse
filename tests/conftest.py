"""Shared fixtures for Claude Pulse tests."""
from __future__ import annotations

import pytest

MOCK_PAYLOAD = {
    "five_hour": {"utilization": 22, "resets_at": "2026-06-10T18:00:00Z"},
    "seven_day": {"utilization": 41, "resets_at": "2026-06-12T03:45:00Z"},
}

# Fable quota exposed via the current ``limits[]`` array format. Includes an
# account-wide entry (``scope: null``) that must be ignored, and a scoped
# entry for a different model to make sure matching keys on display_name.
MOCK_PAYLOAD_FABLE_LIMITS = {
    "five_hour": {"utilization": 22, "resets_at": "2026-06-10T18:00:00Z"},
    "seven_day": {"utilization": 41, "resets_at": "2026-06-12T03:45:00Z"},
    "limits": [
        {"kind": "weekly_all", "percent": 41.0, "resets_at": None, "scope": None},
        {
            "kind": "weekly_scoped",
            "group": "weekly",
            "percent": 63.0,
            "resets_at": "2026-06-12T03:45:00Z",
            "scope": {"model": {"id": None, "display_name": "Fable"}},
        },
    ],
}

# Fable quota exposed via the legacy flat ``seven_day_fable`` key.
MOCK_PAYLOAD_FABLE_FLAT = {
    "five_hour": {"utilization": 22, "resets_at": "2026-06-10T18:00:00Z"},
    "seven_day": {"utilization": 41, "resets_at": "2026-06-12T03:45:00Z"},
    "seven_day_fable": {"utilization": 63, "resets_at": "2026-06-12T03:45:00Z"},
}

# Organization payload (plan detection), trimmed to the fields we read.
MOCK_ORG = {
    "uuid": "11111111-2222-3333-4444-555555555555",
    "name": "test@example.com's Organization",
    "rate_limit_tier": "default_claude_max_5x",
    "capabilities": ["claude_max", "chat"],
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
