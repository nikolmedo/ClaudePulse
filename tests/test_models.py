"""Unit tests for the domain layer (models.py) — no Home Assistant required."""
from __future__ import annotations

from datetime import datetime, timezone

from custom_components.claude_pulse.models import (
    NOT_AVAILABLE,
    ClaudeUsage,
    ResetInfo,
    detect_plan,
    extract_fable,
    parse_reset_timestamp,
)

from .conftest import (
    MOCK_ORG,
    MOCK_PAYLOAD,
    MOCK_PAYLOAD_FABLE_FLAT,
    MOCK_PAYLOAD_FABLE_LIMITS,
)

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


class TestDetectPlan:
    def test_known_tiers(self):
        assert detect_plan({"rate_limit_tier": "default_claude_ai"}) == "Free"
        assert detect_plan({"rate_limit_tier": "default_claude_pro"}) == "Pro"
        assert detect_plan({"rate_limit_tier": "default_claude_max_5x"}) == "Max 5x"
        assert detect_plan({"rate_limit_tier": "default_claude_max_20x"}) == "Max 20x"
        assert detect_plan({"rate_limit_tier": "default_raven"}) == "Team"

    def test_unknown_tier_is_prettified(self):
        assert detect_plan({"rate_limit_tier": "default_claude_ultra_7x"}) == "Ultra 7x"

    def test_capabilities_fallback(self):
        assert detect_plan({"capabilities": ["claude_max", "chat"]}) == "Max"
        assert detect_plan({"capabilities": ["claude_pro", "chat"]}) == "Pro"
        assert detect_plan({"capabilities": ["chat"]}) == "Free"

    def test_tier_wins_over_capabilities(self):
        assert detect_plan(MOCK_ORG) == "Max 5x"

    def test_missing_or_malformed_returns_not_available(self):
        assert detect_plan(None) == NOT_AVAILABLE
        assert detect_plan({}) == NOT_AVAILABLE
        assert detect_plan("garbage") == NOT_AVAILABLE
        assert detect_plan({"rate_limit_tier": None, "capabilities": None}) == (
            NOT_AVAILABLE
        )
        assert detect_plan({"capabilities": ["unrelated"]}) == NOT_AVAILABLE


class TestClaudeUsage:
    def test_from_payload(self):
        usage = ClaudeUsage.from_payload(MOCK_PAYLOAD, now=NOW)
        assert usage.session_pct == 22.0
        assert usage.weekly_pct == 41.0
        assert usage.session_reset.countdown == "2h 30m"
        assert usage.weekly_reset.is_known
        assert usage.plan == NOT_AVAILABLE

    def test_from_payload_with_org(self):
        usage = ClaudeUsage.from_payload(MOCK_PAYLOAD, now=NOW, org=MOCK_ORG)
        assert usage.plan == "Max 5x"

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
        data = ClaudeUsage.from_payload(
            MOCK_PAYLOAD, now=NOW, org=MOCK_ORG
        ).as_sensor_data()
        assert data["session_pct"] == 22.0
        assert data["session_used"] == 22.0
        assert data["session_limit"] == 100.0
        assert data["weekly_pct"] == 41.0
        assert data["session_reset_countdown"] == "2h 30m"
        assert data["plan"] == "Max 5x"

    def test_as_sensor_data_weekly_reset_summary(self):
        data = ClaudeUsage.from_payload(MOCK_PAYLOAD, now=NOW).as_sensor_data()
        assert data["weekly_reset"] == (
            f"{data['weekly_reset_weekday']} @ {data['weekly_reset_time']}"
        )

    def test_as_sensor_data_weekly_reset_unknown(self):
        data = ClaudeUsage.from_payload({}).as_sensor_data()
        assert data["weekly_reset"] == NOT_AVAILABLE


class TestExtractFable:
    def test_limits_array_format(self):
        pct, resets_at = extract_fable(MOCK_PAYLOAD_FABLE_LIMITS)
        assert pct == 63.0
        assert resets_at == "2026-06-12T03:45:00Z"

    def test_flat_key_format(self):
        pct, resets_at = extract_fable(MOCK_PAYLOAD_FABLE_FLAT)
        assert pct == 63.0
        assert resets_at == "2026-06-12T03:45:00Z"

    def test_display_name_match_is_case_insensitive(self):
        payload = {
            "limits": [
                {
                    "kind": "weekly_scoped",
                    "percent": 12.0,
                    "resets_at": "2026-06-12T03:45:00Z",
                    "scope": {"model": {"id": None, "display_name": "FABLE"}},
                }
            ]
        }
        pct, _ = extract_fable(payload)
        assert pct == 12.0

    def test_alternate_flat_key(self):
        payload = {"fable_weekly": {"utilization": 7, "resets_at": None}}
        pct, resets_at = extract_fable(payload)
        assert pct == 7.0
        assert resets_at is None

    def test_absent_returns_none(self):
        assert extract_fable(MOCK_PAYLOAD) == (None, None)
        assert extract_fable({}) == (None, None)

    def test_null_and_malformed_do_not_crash(self):
        assert extract_fable({"limits": None}) == (None, None)
        assert extract_fable({"limits": [None, "x", {}]}) == (None, None)
        assert extract_fable({"seven_day_fable": None}) == (None, None)
        # Scoped entry for a different model must be ignored.
        payload = {
            "limits": [
                {
                    "kind": "weekly_scoped",
                    "percent": 99.0,
                    "resets_at": None,
                    "scope": {"model": {"display_name": "Opus"}},
                }
            ]
        }
        assert extract_fable(payload) == (None, None)


class TestClaudeUsageFable:
    def test_from_payload_limits(self):
        usage = ClaudeUsage.from_payload(MOCK_PAYLOAD_FABLE_LIMITS, now=NOW)
        assert usage.fable_pct == 63.0
        assert usage.fable_reset.is_known

    def test_from_payload_flat(self):
        usage = ClaudeUsage.from_payload(MOCK_PAYLOAD_FABLE_FLAT, now=NOW)
        assert usage.fable_pct == 63.0

    def test_from_payload_absent_keeps_none(self):
        usage = ClaudeUsage.from_payload(MOCK_PAYLOAD, now=NOW)
        assert usage.fable_pct is None
        assert not usage.fable_reset.is_known

    def test_as_sensor_data_fable_present(self):
        data = ClaudeUsage.from_payload(
            MOCK_PAYLOAD_FABLE_LIMITS, now=NOW
        ).as_sensor_data()
        assert data["fable_pct"] == 63.0
        assert data["fable_reset"] != NOT_AVAILABLE

    def test_as_sensor_data_fable_absent(self):
        data = ClaudeUsage.from_payload(MOCK_PAYLOAD, now=NOW).as_sensor_data()
        assert data["fable_pct"] is None
        assert data["fable_reset"] == NOT_AVAILABLE
