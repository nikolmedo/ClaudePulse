"""Constants for the Claude Pulse integration."""

DOMAIN = "claude_pulse"

# Config entry keys
CONF_SESSION_KEY = "session_key"
CONF_ORG_ID = "org_id"
CONF_UPDATE_INTERVAL = "update_interval"
CONF_FABLE_QUOTA = "fable_quota"

# Defaults
DEFAULT_UPDATE_INTERVAL = 120  # seconds
MIN_UPDATE_INTERVAL = 30
DEFAULT_FABLE_QUOTA = True

# Claude API
CLAUDE_BASE_URL = "https://claude.ai"
ENDPOINT_ORG_USAGE = "/api/organizations/{org_id}/usage"
ENDPOINT_USAGE = "/api/usage"
ENDPOINT_ACCOUNT_USAGE = "/api/account/usage"
ENDPOINT_ORG_INFO = "/api/organizations/{org_id}"

CLAUDE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/120.0",
    "Accept": "application/json",
    "Referer": "https://claude.ai/settings/usage",
    "sec-fetch-site": "same-origin",
    "sec-fetch-mode": "cors",
    "sec-fetch-dest": "empty",
}

# Sensor data keys (keys in coordinator.data dict)
KEY_SESSION_PCT = "session_pct"
KEY_WEEKLY_PCT = "weekly_pct"
KEY_SESSION_COUNTDOWN = "session_reset_countdown"
KEY_SESSION_RESET_TIME = "session_reset_time"
KEY_WEEKLY_RESET = "weekly_reset"
KEY_WEEKLY_RESET_WEEKDAY = "weekly_reset_weekday"
KEY_WEEKLY_RESET_TIME = "weekly_reset_time"
KEY_SESSION_USED = "session_used"
KEY_SESSION_LIMIT = "session_limit"
KEY_PLAN = "plan"
KEY_FABLE_PCT = "fable_pct"
KEY_FABLE_RESET = "fable_reset"
