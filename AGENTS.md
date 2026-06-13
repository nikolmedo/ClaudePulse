# AGENTS.md — Claude Pulse

Guidance for AI coding agents (and human contributors) working on this repository.

## What this project is

Claude Pulse is a **Home Assistant custom integration** (HACS, category `integration`) that polls the undocumented Claude.ai usage API and exposes session (5-hour) and weekly (7-day) usage limits as Home Assistant sensors.

- **Language:** Python, fully async (Home Assistant integration conventions)
- **Domain:** `claude_pulse`
- **Minimum Home Assistant version:** 2024.1.0 (see `hacs.json`)
- **No runtime requirements** beyond Home Assistant itself (`manifest.json` → `requirements: []`)

## Architecture

The integration follows a pragmatic Clean Architecture, adapted to the structure Home Assistant imposes. Dependencies point inward — the domain knows nothing about HA or HTTP:

```
┌─────────────────────────────────────────────────────────┐
│ Framework layer (Home Assistant)                        │
│   __init__.py      entry setup/unload                   │
│   coordinator.py   DataUpdateCoordinator (thin adapter) │
│   config_flow.py   setup / reauth / options flows       │
│   sensor.py        declarative sensor entities          │
├─────────────────────────────────────────────────────────┤
│ Infrastructure layer (aiohttp only, no HA imports)      │
│   api.py           ClaudeApiClient + exceptions         │
├─────────────────────────────────────────────────────────┤
│ Domain layer (pure Python, no HA, no aiohttp)           │
│   models.py        ClaudeUsage, ResetInfo, parsing      │
│   const.py         domain constants, endpoints, keys    │
└─────────────────────────────────────────────────────────┘
```

Data flow per update cycle:

1. `ClaudePulseCoordinator._async_update_data` asks `ClaudeApiClient.async_get_usage()` for the raw payload.
2. The client tries endpoints in fallback order: `/api/organizations/{org_id}/usage` → `/api/usage` → `/api/account/usage`. First HTTP 200 wins. HTTP 401/403 raises `ClaudeAuthError`; total failure raises `ClaudeApiError`.
3. The coordinator translates exceptions: `ClaudeAuthError` → `ConfigEntryAuthFailed` (triggers HA's reauth flow), `ClaudeApiError` → `UpdateFailed` (HA retries).
4. `ClaudeUsage.from_payload(raw)` parses the payload into the domain model; `as_sensor_data()` flattens it into the dict the sensor platform reads.
5. `sensor.py` declares sensors via `ClaudePulseSensorDescription` (a `SensorEntityDescription` with a `data_key` mapping into that dict). **Adding a sensor = one description entry + one key in `as_sensor_data()`.**

Rules to preserve:

- `models.py` must stay importable without Home Assistant or aiohttp installed.
- `api.py` must stay importable without Home Assistant; the aiohttp session is injected by the caller.
- Only the framework layer may import from `homeassistant.*`.

## Repository layout

```
custom_components/claude_pulse/   # the integration (see Architecture)
tests/
├── conftest.py                   # MOCK_PAYLOAD, MOCK_CONFIG, custom-integration fixture
├── test_models.py                # domain tests — pure pytest, no HA
├── test_api.py                   # client tests — aioresponses, no HA
├── test_config_flow.py           # setup/reauth/options flows — HA test harness
└── test_init.py                  # entry setup, sensors, unload, reauth trigger
claude_usage.py / claude_usage.yaml  # legacy standalone setup (predates the integration)
hacs.json                         # HACS metadata
pyproject.toml                    # pytest config (asyncio_mode = auto)
requirements_test.txt             # test dependencies
.github/workflows/main.yml        # CI: HACS + Hassfest validation, pytest
```

## Running the tests

```bash
pip install -r requirements_test.txt
python -m pytest tests -v
```

**Windows gotcha:** `pytest-homeassistant-custom-component` pulls in Home Assistant core, which imports Unix-only modules (`fcntl`) and pins `lru-dict==1.3.0` (no Windows cp313 wheel). The HA-dependent tests (`test_config_flow.py`, `test_init.py`) **cannot run natively on Windows**. Run the full suite in a Linux container instead:

```powershell
docker run --rm -v "${PWD}:/app" -w /app python:3.13 `
  sh -c "pip install -r requirements_test.txt && python -m pytest tests -q"
```

Use the full `python:3.13` image, not `-slim` — `lru-dict==1.3.0` has no cp313 wheel and must be compiled, so the image needs `gcc`.

`test_models.py` and `test_api.py` are framework-free and run anywhere with `pytest`, `pytest-asyncio`, `aiohttp`, and `aioresponses`.

## Conventions and gotchas

- **Conventional commits** (`fix:`, `feat:`, `docs:`, `test:`, `refactor:`...). No AI attribution lines in commits.
- **All documentation and code comments in English.**
- **Version bumps** go in `custom_components/claude_pulse/manifest.json` (`version` field); releases are tagged on GitHub (HACS reads releases/tags).
- `strings.json` and `translations/en.json` must stay in sync — Hassfest validates this.
- The Claude.ai usage API is **undocumented and unofficial**; the headers in `const.py` (`CLAUDE_HEADERS`) mimic a browser request and matter — don't strip them.
- API timestamps may be ISO strings **or** epoch seconds **or** epoch milliseconds; `models.py::parse_reset_timestamp` handles all three (`> 1e10` heuristic for milliseconds).
- The `plan` sensor is hardcoded to `"Pro"` in `models.py` — the usage endpoints don't return plan info.
- No blocking I/O anywhere — everything runs in the event loop with the shared aiohttp session.
- `ResetInfo` time/weekday strings are rendered in the **local timezone** (`astimezone()`); tests compute expected values the same way to stay timezone-independent.

## CI

`.github/workflows/main.yml` runs on every push and PR:

1. **HACS validation** (`hacs/action`, category `integration`)
2. **Hassfest validation** (`home-assistant/actions/hassfest`)
3. **pytest** (Python 3.13 on ubuntu-latest, installs `requirements_test.txt`)

Any change must keep all three green.
