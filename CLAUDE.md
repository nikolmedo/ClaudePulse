# CLAUDE.md

See [AGENTS.md](AGENTS.md) for the full project guide: architecture, layering rules, test instructions, conventions, gotchas, and CI requirements.

Quick facts:

- Home Assistant custom integration (HACS), domain `claude_pulse`, fully async.
- Layered: `models.py` (pure domain) ← `api.py` (aiohttp client, no HA) ← coordinator/config_flow/sensor (HA adapters). Keep dependencies pointing inward.
- Tests: `python -m pytest tests`. On Windows, HA-dependent tests require a Linux container (see AGENTS.md → Running the tests).
- Version lives in `custom_components/claude_pulse/manifest.json`.
- Conventional commits; documentation 100% in English.
- CI: HACS action + Hassfest + pytest on every push.
