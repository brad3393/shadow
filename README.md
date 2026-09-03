<div align="center">

<img src="docs/logo.png" alt="Shadow logo" width="140"/>

# Shadow

**A personal, offline-first autonomous AI network.**

Shadow runs on your machine, understands natural-language commands, routes them to
specialized agents, executes them inside a security sandbox, remembers everything
persistently, manages its own task queue, and even builds its own tools.

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org)
[![Tests](https://img.shields.io/badge/tests-86%2F86-brightgreen)](#testing)
[![Dependencies](https://img.shields.io/badge/dependencies-zero-success)](requirements.txt)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20macOS-lightgrey)](install.sh)

</div>

---

## Why Shadow?

Most "AI assistants" are thin clients to a cloud model. Shadow is the opposite:
a **self-contained system** that works fully offline and treats AI as an optional
accelerator, not a dependency.

- **Zero dependencies.** Pure Python standard library. `pip install` nothing.
- **Offline-first.** Every AI-powered feature degrades gracefully to deterministic
  template and rule-based fallbacks when Ollama isn't running.
- **Autonomous.** A daemon mode that plans, executes, and verifies its own work —
  including self-generated maintenance tasks and self-improvement analysis.
- **Sandboxed by design.** Every command passes through the Guardian security
  layer before execution. Dangerous patterns are blocked, checkpoints are taken,
  and actions can be rolled back.
- **Persistent.** Memory, tasks, learned procedures, and custom-built tools all
  survive restarts as local JSON.
- **Extensible.** Drop a new agent file in `agents/` and Shadow discovers it at
  boot. Or let any AI assistant extend it — see [`AI_ONBOARDING.md`](AI_ONBOARDING.md).

## The Agents

| Agent | Responsibility |
|---|---|
| **CodingAgent** | Writes, fixes, refactors, and explains code |
| **ResearchAgent** | Gathers and summarizes information |
| **FileAgent** | Reads, writes, organizes, and searches files |
| **SecurityAgent** | Audits, patches, and monitors system security |
| **SystemAgent** | Translates natural language into shell commands |
| **PlanningAgent** | Breaks goals into executable task plans |
| **TestingAgent** | Generates and runs test suites |
| **LearningAgent** | Learns from documents and past outcomes |
| **DocumentationAgent** | Generates and maintains documentation |
| **HardwareAgent** | Monitors CPU, RAM, storage, battery, and network |

Plus the infrastructure that makes them a *system*:

- **Guardian** — security layer: command auditing, sandboxing, checkpoints, rollback
- **Memory** — 10-category persistent memory (JSON, survives restarts)
- **Task Manager** — priority queue with statuses and dependencies
- **Vault** — custom-built tool storage (Shadow's own toolbox)
- **Bot Factory** — writes, sandbox-tests, and deploys its own new tools via Ollama
- **Self-Improvement** — analyzes error patterns and proposes new capabilities
- **Hardware Monitor** — resource awareness with critical-condition backoff
- **REST API** — token-authenticated HTTP interface for mobile / remote clients

## Architecture

```
                ┌─────────────────────────────────────────┐
                │              ShadowCore                 │
 natural  ───▶  │  command routing · agent discovery      │  ───▶  Guardian
 language      │  autonomous loop · status reporting      │         │ audit · block ·
 commands      └───────────────┬─────────────────────────┘         │ checkpoint · rollback
                                │                                    ▼
                ┌───────────────┴───────────────┐        ┌─────────────────────┐
                │         10 Expert Agents       │◀──────▶│      Ollama (opt.)  │
                │ coding·research·file·security │        │  local LLM (llama3.1)│
                │ system·planning·testing·learn. │        └─────────────────────┘
                │ docs·hardware                  │   every call guarded by
                └───────┬───────────────┬───────┘   is_available() + fallback
                        │               │
              ┌─────────▼───┐   ┌───────▼────────┐
              │ Memory/Vault│   │  Task Manager  │
              │ persistent  │   │  priority queue│
              └─────────────┘   └────────────────┘
```

## Quick Start

```bash
git clone https://github.com/brad3393/shadow.git
cd shadow
./install.sh          # or: python main.py directly
./shadow.sh           # interactive REPL — type /help
```

Run a single command, get a single answer:

```bash
python main.py "show disk usage for the root volume"
python main.py "write a script that renames all .txt files in this folder"
python main.py --status     # JSON system status
```

**Optional — unlock full AI reasoning** (still 100% local):

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.1
```

Without Ollama, Shadow still runs — agents fall back to deterministic
templates and pattern-matching. See [AI_ONBOARDING.md](AI_ONBOARDING.md)
for the offline contract every module follows.

## Usage

### Interactive CLI

```text
/status      system status          /tasks    task queue
/agents      agent roster           /memory   memory browser
/hardware    resource report        /autonomous  run one autonomous cycle
/restart     reboot core            /clear    clear screen
/help        all commands           /quit     exit
```

### Daemon Mode

```bash
python main.py --daemon --interval 30          # persistent loop
python main.py --autonomous                    # single autonomous cycle
```

Each daemon cycle: hardware check → auto-generate maintenance tasks →
process the queue → self-improvement analysis (every 5 cycles) →
checkpoint cleanup (every 10 cycles) → write heartbeat. A `heartbeat.json`
file lets any external monitor confirm Shadow is alive.

`install.sh` can register Shadow as a **systemd** (Linux) or **launchd**
(macOS) service so it survives reboots.

### REST API (for mobile & remote clients)

```bash
python api_server.py --host 0.0.0.0 --port 8787 --token YOUR_SECRET
```

| Endpoint | Method | Purpose |
|---|---|---|
| `/health` | GET | Liveness + last heartbeat |
| `/api/status` | GET | Full system status |
| `/api/agents` | GET | Registered agents & capabilities |
| `/api/tasks` | GET / POST | List / create tasks |
| `/api/memory` | GET | Memory summary |
| `/api/command` | POST | Execute any natural-language command |
| `/api/autonomous` | POST | Trigger an autonomous cycle remotely |

All requests require `Authorization: Bearer YOUR_SECRET` when a token is set.
The Guardian audits API-executed commands exactly like CLI ones.

### Building a Mobile Client

The recommended architecture: Shadow stays on your machine, the mobile app is a
thin client to the REST API. React Native or Flutter against the endpoints above
is enough — keep all business logic on the Python side. Step-by-step guide in
[AI_ONBOARDING.md](AI_ONBOARDING.md#how-to-build-mobile-versions).

## Extending Shadow

The extension pattern is deliberately small:

1. Copy any agent in `agents/`
2. Set its `name`, `description`, `keywords`
3. Implement `can_handle()` and `execute()`
4. Shadow auto-discovers it at boot — no registration code

Adding an API endpoint, memory category, or vault tool follows the same
copy-and-specialize pattern. Full guides, conventions, and safety rules in
[AI_ONBOARDING.md](AI_ONBOARDING.md) (written for AI assistants and humans alike).

**Safety contract for any contributor (human or AI):**

- Guardian checks are never weakened or bypassed
- Self-improvement may never modify `guardian/`
- Every Ollama call is guarded with a working offline fallback
- Stdlib only — no hard external dependencies, ever

## Testing

```bash
python tests/test_shadow.py
```

86 integration tests cover boot, routing, all ten agents, Guardian enforcement,
memory persistence, task lifecycle, vault tools, the API server, and the
autonomous loop. CI runs the suite on Python 3.10–3.12 for every push and PR.

## Project Structure

```
shadow/
├── main.py            # entry: REPL, single commands, --status/--daemon/--autonomous
├── api_server.py      # REST API (stdlib http.server, token auth)
├── install.sh         # installer + systemd/launchd auto-start
├── core/              # ShadowCore orchestrator + BaseAgent
├── agents/            # 10 expert agents (auto-discovered)
├── guardian/          # security: audit, sandbox, checkpoint, rollback
├── memory/            # persistent 10-category memory
├── tasks/             # task manager
├── vault/             # custom tool storage
├── botfactory/        # self-building tools (Ollama-gated)
├── self_improve/      # error-pattern analysis, capability proposals
├── hardware/          # resource monitoring
├── registry/          # dynamic capability registry
├── ollama/            # OllamaInterface (availability-guarded)
├── learning/          # document learning system
├── config/            # paths, env, core principles
├── logging/           # ShadowLogger
├── ui/                # interactive CLI
├── tests/             # 86-test integration suite
└── shadow_data/       # runtime data (created at first run, gitignored)
```

## License

[MIT](LICENSE) © 2026 Brad Randa

---

*Shadow was built by Brad Randa with the assistance of Solene (Base44 Superagent).*

## ShadowOS — dedicated appliance mode

Have an old laptop? Turn it into a dedicated Shadow machine: minimal
Debian stripped to one job, booting **straight into Shadow's console** —
no desktop, no login screen. The REST API comes up with it, and Shadow's
AI calls route to a beefier machine's Ollama over Tailscale.

```
power button → 15s → Shadow console (fullscreen) + API :8787
```

See [shadowos/README_SHADOWOS.md](shadowos/README_SHADOWOS.md) for the
45-minute install guide and [shadowos/install-shadowos.sh](shadowos/install-shadowos.sh)
for the one-command installer.
