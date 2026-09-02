# AI_ONBOARDING.md — Read This First

> **This document is written for AI assistants** (Claude, ChatGPT, Copilot, Cursor, Gemini, or any LLM-based coding agent). If you are an AI that has been given this codebase, this file gives you everything you need to understand, modify, and extend it — including how to build **mobile versions**.

---

## What this codebase is

**Shadow** is a personal, offline-capable, autonomous AI network written in pure Python (3.10+, stdlib only — zero dependencies). It runs on a local machine, accepts natural-language commands, routes them to specialized agents, executes them inside a security sandbox, remembers everything persistently, manages a task queue autonomously, and builds its own tools.

- **Size:** 5,332+ lines, 28 modules
- **Tests:** 86/86 passing (`python tests/test_shadow.py` or `./shadow.sh --test`)
- **LLM:** Optional local Ollama (llama3.1). Everything degrades gracefully without it — offline-first is a core design constraint. NEVER add a hard dependency on any cloud service.

## Module map

```
shadow/
├── main.py               # Entry point: REPL, --status, --daemon, --autonomous, --test
├── api_server.py          # REST API over HTTP (stdlib) — THE INTERFACE FOR MOBILE APPS
├── install.sh             # One-command installer (Linux/macOS, systemd/launchd auto-start)
├── core/
│   ├── shadow_core.py     # ShadowCore orchestrator — boots agents, routes commands
│   └── base.py            # BaseAgent — every agent inherits from this
├── agents/                # 10 expert agents, all follow the same pattern:
│   ├── coding_agent.py     #   __init__(ollama, guardian), can_handle(desc), execute(task)
│   ├── research_agent.py
│   ├── file_agent.py
│   ├── security_agent.py
│   ├── system_agent.py
│   ├── planning_agent.py
│   ├── testing_agent.py
│   ├── learning_agent.py
│   ├── documentation_agent.py
│   └── hardware_agent.py
├── guardian/              # Security layer: blocks dangerous ops, checkpoints, rollback
│   ├── guardian.py        #   guardian.sh = checkpoint/rollback CLI
├── memory/                # Persistent JSON memory (10 categories)
├── tasks/                 # Task manager: priority queue, statuses, dependencies
├── vault/                 # Tool/knowledge storage (Shadow's toolbox)
├── botfactory/            # Self-building tools: Ollama generates code → sandbox test → deploy
├── self_improve/          # Error pattern analysis, missing-capability detection
├── hardware/              # CPU/RAM/battery/storage/network monitor
├── registry/              # Dynamic capability registry (agents + tools)
├── ollama/                # OllamaInterface — is_available() checked before EVERY use
├── learning/              # Document learning system (needs Ollama)
├── config/                # config.py (paths/env) + core_principles.json (safety rules)
├── logging/               # ShadowLogger — always use, never print()
├── ui/
│   └── cli.py             # Interactive REPL with slash commands
├── tests/
│   └── test_shadow.py     # 86 integration tests — RUN THESE after every change
└── shadow_data/           # Created at runtime: tasks.json, memory.json, heartbeat.json, pid
```

## Architecture in one paragraph

`ShadowCore.boot()` discovers all agents, asks each `can_handle(task_description)` (keyword matching), and routes incoming commands to the best match. Every command flows through the **Guardian** first — it blocks dangerous shell patterns (recursive deletes, forced chmod, writes to system paths), enforces sandbox boundaries, and keeps an audit log. Agents return `{"success": bool, "output": str, "agent": str}` dicts. Results are stored in the **Vault** / **Memory** (JSON, survives restarts). The **daemon** (`main.py --daemon`) runs a 30s loop that auto-generates maintenance tasks, processes the queue, runs self-improvement every 5 cycles, and writes a heartbeat to `shadow_data/heartbeat.json`.

## How to add a new agent (the #1 extension)

1. Copy `agents/documentation_agent.py` → `agents/your_agent.py`
2. Subclass `BaseAgent`, set `name`, `description`, and `keywords` (lowercase strings matched against the task description)
3. Implement `can_handle()` and `execute()`; return `{"success", "output", "agent"}`
4. ShadowCore auto-discovers it at boot — no registration code needed
5. Add tests in `tests/test_shadow.py` (agent boots, handles a keyword, rejects non-matching)
6. Run `python tests/test_shadow.py` — all 86+ must pass

## How to add a new API endpoint

`api_server.py` is stdlib `http.server`. Add a handler in `do_GET` or `do_POST` following the existing pattern: check auth → parse body → call `self.core.<subsystem>` → `_send_json()`. Keep it JSON in/out. Guardian runs inside `core.receive_command()`, so API calls are sandboxed the same as CLI calls.

## How to build MOBILE VERSIONS

The mobile app should be a **thin client** to `api_server.py`. Shadow stays on the desktop/Mac; the phone talks to it over HTTP.

**1. Start the API on the machine (LAN):**
```bash
python api_server.py --host 0.0.0.0 --port 8787 --token MYSECRET
```

**2. Endpoints the app uses:**
| Endpoint | Method | Purpose |
|---|---|---|
| `/health` | GET | Connection check + last heartbeat |
| `/api/status` | GET | Dashboard: agents, tasks, memory, hardware |
| `/api/command` | POST `{"command": "..."}` | Send any natural-language command |
| `/api/agents` | GET | Agent list for the UI |
| `/api/tasks` | GET/POST | Task list / create tasks |
| `/api/autonomous` | POST | Trigger an autonomous cycle remotely |
| `/api/memory` | GET | Browse Shadow's memory |

All requests need header `Authorization: Bearer MYSECRET` if a token is set.

**3. Mobile app recommendations:**
- **React Native / Expo:** fetch() the endpoints above. Screens: Status dashboard, Chat (command input), Tasks list, Memory browser.
- **Flutter:** same endpoints, use `http` package.
- Keep ALL business logic on the Python side — the app is just JSON + rendering.
- For remote (non-LAN) access: recommend Tailscale on both devices rather than opening ports.

**4. If a true standalone mobile port is wanted:** Python runs on Android via Termux/Pydroid, or use BeeWare/Kivy. `ShadowCore` and everything under `core/`, `agents/`, `memory/`, `tasks/`, `guardian/` are platform-independent — only `hardware/` (psutil-free stdlib probes) and `system_agent/` (shell commands) need platform-specific behavior detection.

## Rules any AI must follow when modifying this code

1. **Offline-first.** Every Ollama call must be guarded: `if self.ollama and self.ollama.is_available():` — with a working template/stub fallback. No cloud dependencies, ever.
2. **Guardian is sacred.** Do not weaken, bypass, or remove Guardian checks. Self-improvement must never be allowed to modify `guardian/` — this is enforced, keep it that way.
3. **Stdlib only.** No pip dependencies. If a module needs one anyway, it must degrade gracefully when the import fails.
4. **Test gate.** After any change: `python tests/test_shadow.py` → 0 failures. Add new tests for new behavior.
5. **Log, don't print.** Use `ShadowLogger.get("shadow.<module>")`.
6. **JSON returns.** Agents and API handlers return dicts with a `success` key.
7. **Persistence.** Runtime data goes in `shadow_data/` (gitignore-style: never ship it in archives).
8. **Natural language in, domain commands out.** Agents translate NL ("show disk usage") into concrete domain actions (e.g., `df -h`). Follow the pattern table in `system_agent.py`.

## Quick verification commands

```bash
python tests/test_shadow.py                    # full test suite
python main.py --status                        # JSON status dump
python main.py "show the current date"         # single command
python api_server.py --port 8787 &             # API server
curl -s localhost:8787/health                  # check API
```

Build v1.1 — September 2, 2026. Original build by Brad Randa with Solene (Base44 Superagent).
