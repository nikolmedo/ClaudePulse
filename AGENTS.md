# AGENTS.md — Claude Pulse

Guidance for AI coding agents (and human contributors) working on this repository.

## What this project is

Claude Pulse is a **Home Assistant custom integration** (HACS, category `integration`) that polls the undocumented Claude.ai usage API and exposes session (5-hour) and weekly (7-day) usage limits as Home Assistant sensors.

- **Language:** Python (Home Assistant integration conventions, `async`/`await` throughout)
- **Domain:** `claude_pulse`
- **Minimum Home Assistant version:** 2024.1.0 (see `hacs.json`)
- **No external Python requirements** — uses only Home Assistant helpers (`aiohttp` session, `DataUpdateCoordinator`)

## Repository layout

```
custom_components/claude_pulse/
├── __init__.py          # Entry setup/unload, coordinator wiring
├── config_flow.py       # UI setup flow + re-auth flow + options flow
├── const.py             # Domain, config keys, API endpoints, headers, data keys
├── coordinator.py       # DataUpdateCoordinator — fetches and parses usage data
├── sensor.py            # 10 sensor entity descriptions + entity class
├── manifest.json        # Integration manifest (version lives here)
├── strings.json         # UI strings
├── translations/en.json # English translations (must mirror strings.json)
└── brand/               # Icon assets
claude_usage.py          # Legacy standalone script (predates the integration)
claude_usage.yaml        # Legacy command_line/template sensor package
hacs.json                # HACS metadata
.github/workflows/main.yml  # CI: HACS validation + Hassfest validation
```

## Architecture

1. **`ClaudePulseCoordinator`** (`coordinator.py`) polls Claude.ai endpoints in fallback order: org-scoped usage (`/api/organizations/{org_id}/usage`) → `/api/usage` → `/api/account/usage`. First HTTP 200 wins.
2. Auth is a single `sessionKey` cookie. HTTP 401/403 raises `ConfigEntryAuthFailed`, which triggers Home Assistant's built-in **re-auth flow** (`config_flow.py::async_step_reauth`).
3. The API response shape is `{"five_hour": {"utilization": <int>, "resets_at": <ts>}, "seven_day": {...}}`. The coordinator normalizes it into a flat dict whose keys are defined in `const.py` (`KEY_*`).
4. **`sensor.py`** declares sensors declaratively via `ClaudePulseSensorDescription` (a `SensorEntityDescription` subclass with a `data_key` field mapping to the coordinator dict). Adding a sensor = adding one description entry + a key in the coordinator output.
5. All entities share one `DeviceInfo` (one "Claude Pulse" device per config entry). Unique IDs are `{entry_id}_{description.key}`.

## Conventions and gotchas

- **Conventional commits** (`fix:`, `feat:`, `docs:`, ...). No AI attribution lines in commits.
- **Version bumps** go in `custom_components/claude_pulse/manifest.json` (`version` field) and should be tagged for releases (HACS reads GitHub releases/tags).
- `strings.json` and `translations/en.json` must stay in sync — Hassfest validates this.
- The Claude.ai usage API is **undocumented and unofficial**; headers in `const.py` (`CLAUDE_HEADERS`) mimic a browser request and matter — don't strip them.
- Timestamps from the API may be ISO strings **or** epoch (seconds or milliseconds); `coordinator.py::_parse_timestamp` handles all three.
- The `plan` sensor value is currently hardcoded to `"Pro"` in `coordinator.py` — the usage endpoints don't return plan info.
- Don't add blocking I/O — everything runs in the event loop using Home Assistant's shared `aiohttp` client session.

## Validation / CI

There is no unit test suite. CI (`.github/workflows/main.yml`) runs on every push and PR:

- **HACS action** (`hacs/action`, category `integration`)
- **Hassfest** (`home-assistant/actions/hassfest`)

Any change to `manifest.json`, `strings.json`, translations, or repository structure must keep both green.

## Documentation rules

- All documentation (README, code comments, docstrings) is written **in English**.
- `README.md` is user-facing: keep the HACS *"Add to My Home Assistant"* badge, installation steps, credential instructions, and the sensor table accurate when behavior changes.
