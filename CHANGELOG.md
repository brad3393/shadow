# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [1.1.0] — 2026-09-02

### Added
- `api_server.py` — REST API server (stdlib only) with bearer-token auth,
  enabling mobile and remote clients: `/health`, `/api/status`, `/api/agents`,
  `/api/tasks` (GET/POST), `/api/memory`, `/api/command`, `/api/autonomous`.
- `AI_ONBOARDING.md` — complete onboarding document for AI assistants:
  architecture, module map, extension patterns, safety rules, and a
  step-by-step mobile development guide.
- Repository hygiene: README, LICENSE (MIT), CONTRIBUTING, SECURITY policy,
  CHANGELOG, CI workflow, .gitignore.
- Daemon heartbeat (`shadow_data/heartbeat.json`) for external liveness checks.

### Changed
- SystemAgent natural-language → shell-command translation hardened via an
  explicit pattern table, improving offline reliability.
- Agent keyword routing refined to resolve cross-agent conflicts.
- File paths normalized across all modules.

## [1.0.0] — 2026-09-02

### Added
- ShadowCore orchestrator with automatic agent discovery and command routing.
- Ten expert agents: Coding, Research, File, Security, System, Planning,
  Testing, Learning, Documentation, Hardware.
- Guardian security layer: command auditing, dangerous-pattern blocking,
  sandboxing, checkpoints, and rollback.
- Persistent 10-category memory and task manager with priority queue.
- Vault for custom-built tools; Bot Factory (Ollama-gated) that writes,
  sandbox-tests, and deploys new tools.
- Self-improvement system: error-pattern analysis and capability proposals.
- Hardware monitoring with critical-condition backoff.
- Interactive CLI (`/status`, `/agents`, `/tasks`, `/memory`, `/hardware`,
  `/autonomous`, `/restart`, `/clear`, `/help`, `/quit`).
- Daemon mode with auto-generated maintenance tasks.
- `install.sh` with systemd (Linux) / launchd (macOS) auto-start.
- 86-test integration suite.
