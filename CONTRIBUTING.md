# Contributing to Shadow

Thanks for helping make Shadow better — human or AI, the rules are the same.

## Ground rules

1. **Offline-first is the contract.** Every Ollama call must be guarded:
   `if self.ollama and self.ollama.is_available():` — with a working
   deterministic fallback. No cloud dependencies, ever.
2. **Guardian is sacred.** Never weaken, bypass, or remove Guardian checks.
   Self-improvement code may not modify `guardian/` — this is enforced
   deliberately; keep it that way.
3. **Stdlib only.** No pip dependencies. If a module truly needs one, it must
   degrade gracefully when the import fails.
4. **Test gate.** After any change: `python tests/test_shadow.py` → 0 failures.
   Add tests for new behavior. CI enforces this on every push.
5. **Log, don't print.** Use `ShadowLogger.get("shadow.<module>")`.
6. **JSON returns.** Agents and API handlers return dicts with a `success` key.

## Adding a new agent

1. Copy the simplest existing agent (`agents/documentation_agent.py`).
2. Subclass `BaseAgent`; set `name`, `description`, `keywords`.
3. Implement `can_handle()` and `execute()`.
4. Shadow auto-discovers it at boot — no registration code needed.
5. Add tests; run the suite.

## Adding an API endpoint

Follow the existing pattern in `api_server.py`: check auth → parse body →
call `self.core.<subsystem>` → `_send_json()`. JSON in, JSON out. The
Guardian applies to API commands exactly as to CLI commands.

## Pull requests

- Keep PRs focused: one feature or fix per PR.
- Run the test suite locally before pushing.
- Update `CHANGELOG.md` under an `Unreleased` heading.

For guidance aimed specifically at AI coding assistants, see
[AI_ONBOARDING.md](AI_ONBOARDING.md).
