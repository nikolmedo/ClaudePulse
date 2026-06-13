"""Domain models for Claude Pulse.

Pure Python — no Home Assistant imports. Everything in this module is
unit-testable without the HA test harness.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

NOT_AVAILABLE = "N/A"


@dataclass(frozen=True)
class ResetInfo:
    """Display-friendly representation of a usage-window reset timestamp."""

    date: str = NOT_AVAILABLE
    time: str = NOT_AVAILABLE
    weekday: str = NOT_AVAILABLE
    countdown: str = NOT_AVAILABLE

    @property
    def is_known(self) -> bool:
        """Whether the reset timestamp could be parsed."""
        return self.weekday != NOT_AVAILABLE


def parse_reset_timestamp(ts, now: datetime | None = None) -> ResetInfo:
    """Parse an ISO or epoch timestamp into a ResetInfo.

    Accepts ISO-8601 strings (with or without trailing ``Z``), epoch seconds,
    or epoch milliseconds. Returns an empty ResetInfo on any parse failure.
    """
    if not ts:
        return ResetInfo()
    try:
        if isinstance(ts, (int, float)):
            if ts > 1e10:  # heuristic: epoch milliseconds
                ts /= 1000
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        else:
            dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        now = now or datetime.now(tz=timezone.utc)
        remaining = max(0.0, (dt - now).total_seconds())
        hours = int(remaining // 3600)
        minutes = int((remaining % 3600) // 60)
        loc = dt.astimezone()
        return ResetInfo(
            date=loc.strftime("%b %d"),
            time=loc.strftime("%I:%M %p"),
            weekday=loc.strftime("%A"),
            countdown=f"{hours}h {minutes}m" if hours else f"{minutes}m",
        )
    except (ValueError, OverflowError, OSError):
        return ResetInfo()


@dataclass(frozen=True)
class ClaudeUsage:
    """A snapshot of Claude.ai usage limits."""

    session_pct: float
    weekly_pct: float
    session_reset: ResetInfo
    weekly_reset: ResetInfo
    plan: str = "Pro"

    @classmethod
    def from_payload(cls, raw: dict, now: datetime | None = None) -> ClaudeUsage:
        """Build a ClaudeUsage from the raw claude.ai usage API payload.

        Expected shape::

            {"five_hour": {"utilization": 22, "resets_at": "..."},
             "seven_day": {"utilization": 7, "resets_at": "..."}}
        """
        sess = raw.get("five_hour") or {}
        week = raw.get("seven_day") or {}
        return cls(
            session_pct=float(sess.get("utilization") or 0),
            weekly_pct=float(week.get("utilization") or 0),
            session_reset=parse_reset_timestamp(sess.get("resets_at"), now),
            weekly_reset=parse_reset_timestamp(week.get("resets_at"), now),
        )

    def as_sensor_data(self) -> dict:
        """Flatten into the dict consumed by the sensor platform."""
        weekly = self.weekly_reset
        return {
            "session_pct":             self.session_pct,
            "session_used":            self.session_pct,
            "session_limit":           100.0,
            "session_reset_time":      self.session_reset.time,
            "session_reset_countdown": self.session_reset.countdown,
            "weekly_pct":              self.weekly_pct,
            "weekly_reset_date":       weekly.date,
            "weekly_reset_time":       weekly.time,
            "weekly_reset_weekday":    weekly.weekday,
            "weekly_reset":            (
                f"{weekly.weekday} @ {weekly.time}"
                if weekly.is_known
                else NOT_AVAILABLE
            ),
            "plan":       self.plan,
            "fetched_at": datetime.now().strftime("%H:%M"),
        }
