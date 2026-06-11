# CLAUDE.md

See [AGENTS.md](AGENTS.md) for the full project guide: architecture, repository layout, conventions, gotchas, and CI requirements.

Quick facts:

- Home Assistant custom integration (HACS), domain `claude_pulse`, all code async.
- Version lives in `custom_components/claude_pulse/manifest.json`.
- Conventional commits, documentation 100% in English.
- No test suite — CI validates with HACS action + Hassfest on every push.
