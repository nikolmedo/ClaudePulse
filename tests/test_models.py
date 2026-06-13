"""Unit tests for the domain layer (models.py) — no Home Assistant required."""
from __future__ import annotations

from datetime import datetime, timezone

from custom_components.claude_pulse.models import (
    NOT_AVAILABLE,
    ClaudeUsage,
    ResetInfo,
    parse_reset_timestamp,
)

from .conftest import MOCK_PAYLOAD

NOW = datetime(2026, 6, 10, 15, 30, 0, tzinfo=timezone.utc)


class TestParseResetTimestamp:
    def test_iso_string_with_z_suffix(self):
        info = parse_reset_timestamp("2026-06-10T18:00:00Z", now=NOW)
        expected_local = datetime(2026, 6, 10, 18, 0, tzinfo=timezone.utc).astimezone()
        assert info.countdown == "2h 30m"
        assert info.weekday == expected_local.strftime("%A")
        assert info.time == expected_local.strftime("%I:%M %p")
        assert info.date == expected_local.strftime("%b %d")
        assert info.is_known

    def test_iso_string_with_offset(self):
        info = parse_reset_timestamp("2026-06-10T18:00:00+00:00", now=NOW)
        assert info.countdown == "2h 30m"

    def test_epoch_seconds(self):
        ts = datetime(2026, 6, 10, 16, 15, tzinfo=timezone.utc).timestamp()
        info = parse_reset_timestamp(ts, now=NOW)
        assert info.countdown == "45m"

    def test_epoch_milliseconds(self):
        ts = datetime(2026, 6, 10, 16, 15, tzinfo=timezone.utc).timestamp() * 1000
        info = parse_reset_timestamp(ts, now=NOW)
        assert info.countdown == "45m"

    def test_under_one_hour_omits_hours(self):
        info = parse_reset_timestamp("2026-06-10T15:59:00Z", now=NOW)
        assert info.countdown == "29m"

    def test_past_timestamp_clamps_to_zero(self):
        info = parse_reset_timestamp("2026-06-10T10:00:00Z", now=NOW)
        assert info.countdown == "0m"

    def test_none_returns_fallback(self):
        assert parse_reset_timestamp(None) == ResetInfo()

    def test_empty_string_returns_fallback(self):
        assert parse_reset_timestamp("") == ResetInfo()

    def test_garbage_returns_fallback(self):
        info = parse_reset_timestamp("not-a-date")
        assert info == ResetInfo()
        assert not info.is_known
        assert info.countdown == NOT_AVAILABLE


class TestClaudeUsage:
    def test_from_payload(self):
        usage = ClaudeUsage.from_payload(MOCK_PAYLOAD, now=NOW)
        assert usage.session_pct == 22.0
        assert usage.weekly_pct == 41.0
        assert usage.session_reset.countdown == "2h 30m"
        assert usage.weekly_reset.is_known
        assert usage.plan == "Pro"

    def test_from_empty_payload(self):
        usage = ClaudeUsage.from_payload({})
        assert usage.session_pct == 0.0
        assert usage.weekly_pct == 0.0
        assert not usage.session_reset.is_known

    def test_from_payload_with_null_windows(self):
        usage = ClaudeUsage.from_payload({"five_hour": None, "seven_day": None})
        assert usage.session_pct == 0.0
        assert usage.weekly_pct == 0.0

    def test_as_sensor_data_keys(self):
        data = ClaudeUsage.from_payload(MOCK_PAYLOAD, now=NOW).as_sensor_data()
        assert data["session_pct"] == 22.0
        assert data["session_used"] == 22.0
        assert data["session_limit"] == 100.0
        assert data["weekly_pct"] == 41.0
        assert data["session_reset_countdown"] == "2h 30m"
        assert data["plan"] == "Pro"

    def test_as_sensor_data_weekly_reset_summary(self):
        data = ClaudeUsage.from_payload(MOCK_PAYLOAD, now=NOW).as_sensor_data()
        assert data["weekly_reset"] == (
            f"{data['weekly_reset_weekday']} @ {data['weekly_reset_time']}"
        )

    def test_as_sensor_data_weekly_reset_unknown(self):
        data = ClaudeUsage.from_payload({}).as_sensor_data()
        assert data["weekly_reset"] == NOT_AVAILABLE
