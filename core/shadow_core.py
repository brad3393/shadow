"""
Shadow Core — the central orchestrator.

Responsibilities:
  - Receive user commands and long-term goals
  - Break large goals into smaller tasks
  - Determine which expert agent handles each task
  - Maintain persistent memory
  - Maintain the task queue
  - Communicate with Ollama/local LLMs
  - Coordinate specialized agents
  - Monitor system state
  - Verify results before considering a task complete
  - Learn from successes and failures
  - Manage the Vault (tool/script/knowledge storage)
  - Run self-improvement analysis
"""
import json
import importlib
from pathlib import Path
from typing import Any, Optional

from config.config import *
from core.base import BaseAgent
from logging.logger import ShadowLogger

log = ShadowLogger.get("shadow.core")


class ShadowCore:
    """The heart of the Shadow system."""

    def __init__(self):
        self.agents: dict[str, BaseAgent] = {}
        self.memory = None
        self.task_manager = None
        self.ollama = None
        self.guardian = None
        self.hardware = None
        self.capability_registry = None
        self.vault = None
        self.self_improvement = None
        self._running = False

    # ─── Initialization ────────────────────────────────────────────
    def boot(self):
        """Initialize all subsystems and register agents."""
        log.info("Shadow Core booting...")

        # Import and init subsystems (lazy to avoid circular deps)
        from memory.memory_system import MemorySystem
        from tasks.task_manager import TaskManager
        from ollama.ollama_interface import OllamaInterface
        from guardian.guardian import Guardian
        from hardware.hardware_monitor import HardwareMonitor
        from registry.capability_registry import CapabilityRegistry
        from vault.vault import Vault
        from self_improve.self_improvement import SelfImprovement

        self.memory = MemorySystem()
        self.task_manager = TaskManager()
        self.ollama = OllamaInterface()
        self.guardian = Guardian()
        self.hardware = HardwareMonitor()
        self.capability_registry = CapabilityRegistry()
        self.vault = Vault()
        self.self_improvement = SelfImprovement(core=self)

        # Register built-in expert agents
        self._register_agents()

        # Store core principles
        self._load_core_principles()

        log.info(f"Shadow Core online. {len(self.agents)} agents registered.")

    def _register_agents(self):
        """Dynamically discover and register all expert agents."""
        agents_dir = Path(__file__).parent.parent / "agents"
        for agent_file in sorted(agents_dir.glob("*_agent.py")):
            module_name = f"agents.{agent_file.stem}"
            try:
                mod = importlib.import_module(module_name)
                # Find the agent class (convention: ClassName ends with "Agent")
                for attr_name in dir(mod):
                    attr = getattr(mod, attr_name)
                    if (isinstance(attr, type)
                            and issubclass(attr, BaseAgent)
                            and attr is not BaseAgent
                            and attr_name.endswith("Agent")):
                        instance = attr()
                        self.agents[instance.name] = instance
                        self.capability_registry.register_agent(instance.name, instance.description)
                        log.info(f"  Registered agent: {instance.name}")
            except Exception as e:
                log.warning(f"  Failed to load agent {module_name}: {e}")

    def _load_core_principles(self):
        """Load foundational principles — stored separately from editable memory."""
        principles_file = Path(__file__).parent.parent / "config" / "core_principles.json"
        if principles_file.exists():
            with open(principles_file) as f:
                principles = json.load(f)
            self.memory.store("core_principles", "principles", principles)
            log.info("Core principles loaded.")
        else:
            log.warning("Core principles file not found — using defaults.")

    # ─── Command Processing ───────────────────────────────────────
    def receive_command(self, command: str, context: Optional[dict] = None) -> dict:
        """Entry point for user commands."""
        log.info(f"Command received: {command[:100]}")

        # Check hardware state — pause if critical
        hw = self.hardware.get_status()
        if hw.get("battery_critical") or hw.get("storage_critical"):
            return {
                "success": False,
                "output": "System resources critical. Nonessential operations paused. "
                          f"Battery: {hw.get('battery_pct', '?')}%, "
                          f"Storage free: {hw.get('storage_free_pct', '?')}%",
                "paused": True,
            }

        # Check if this is a goal that needs decomposition
        if self._is_complex_goal(command):
            return self._handle_goal(command, context or {})
        else:
            return self._handle_direct_command(command, context or {})

    def _is_complex_goal(self, command: str) -> bool:
        """Heuristic: if the command mentions multiple steps or is a long-term goal."""
        goal_markers = ["then", "after that", "build", "create a", "set up",
                        "design", "develop", "automate", "organize", "plan"]
        cmd_lower = command.lower()
        return any(m in cmd_lower for m in goal_markers) and len(command) > 50

    def _handle_goal(self, goal: str, context: dict) -> dict:
        """Decompose a complex goal into tasks."""
        log.info(f"Decomposing goal: {goal[:80]}")

        # Ask Ollama to break it down (if available), else simple split
        if self.ollama.is_available():
            prompt = (
                f"Break this goal into 1-6 concrete, actionable tasks. "
                f"Return ONLY a JSON array of strings, each a single task description.\n"
                f"Goal: {goal}"
            )
            response = self.ollama.generate(prompt)
            try:
                tasks = json.loads(response)
                if not isinstance(tasks, list):
                    tasks = [response]
            except json.JSONDecodeError:
                tasks = [response]
        else:
            tasks = [goal]

        # Create tasks in the task manager
        created = []
        for task_desc in tasks:
            agent_name = self._select_agent(task_desc)
            task = self.task_manager.create_task(
                description=task_desc,
                required_agent=agent_name,
                priority="normal",
            )
            created.append(task)

        # Execute tasks
        results = []
        for task in created:
            result = self._execute_task(task)
            results.append(result)

        return {
            "success": all(r.get("success") for r in results),
            "output": json.dumps(results, indent=2),
            "tasks_created": len(created),
        }

    def _handle_direct_command(self, command: str, context: dict) -> dict:
        """Handle a simple direct command."""
        agent_name = self._select_agent(command)
        task = self.task_manager.create_task(
            description=command,
            required_agent=agent_name,
            priority="normal",
        )
        return self._execute_task(task)

    def _select_agent(self, task_description: str) -> str:
        """Determine which expert agent should handle a task."""
        best_match = None
        best_score = 0

        for name, agent in self.agents.items():
            try:
                if agent.can_handle(task_description):
                    # Simple: first match wins, but could be enhanced with scoring
                    return name
            except Exception:
                continue

        # Fallback: ask Ollama to pick, or use a generic agent
        if self.ollama.is_available():
            agent_list = "\n".join(f"- {n}: {a.description}" for n, a in self.agents.items())
            prompt = (
                f"Which agent should handle this task? Reply with ONLY the agent name.\n"
                f"Agents:\n{agent_list}\n\nTask: {task_description}"
            )
            chosen = self.ollama.generate(prompt).strip().lower()
            if chosen in self.agents:
                return chosen

        # Ultimate fallback: coding agent (most general)
        return "coding_agent" if "coding_agent" in self.agents else list(self.agents.keys())[0]

    # ─── Task Execution ───────────────────────────────────────────
    def _execute_task(self, task: dict) -> dict:
        """Execute a single task with the appropriate agent."""
        task_id = task["id"]
        agent_name = task.get("required_agent", "")
        log.info(f"Executing task {task_id} with agent '{agent_name}'")

        self.task_manager.update_task(task_id, status="in_progress")

        agent = self.agents.get(agent_name)
        if not agent:
            error_msg = f"Agent '{agent_name}' not found"
            log.error(error_msg)
            self.task_manager.update_task(task_id, status="failed", error=error_msg)
            self._learn_from_result(task, {"success": False, "error": error_msg})
            self.self_improvement.record_error(agent_name, task["description"], error_msg)
            return {"success": False, "error": error_msg, "task_id": task_id}

        # Guardian pre-check
        allowed, reason = self.guardian.pre_check("agent_execute", {
            "agent": agent_name,
            "task": task["description"],
        })
        if not allowed:
            log.warning(f"Guardian blocked task {task_id}: {reason}")
            self.task_manager.update_task(task_id, status="blocked", error=reason)
            self.self_improvement.record_error(agent_name, task["description"], f"Guardian blocked: {reason}")
            return {"success": False, "error": f"Blocked by Guardian: {reason}", "task_id": task_id}

        try:
            result = agent.execute(task)

            # Verify result
            if self._verify_result(task, result):
                self.task_manager.update_task(
                    task_id,
                    status="completed",
                    result=result.get("output", ""),
                )
                self._learn_from_result(task, result)
                log.info(f"Task {task_id} completed successfully.")
                return {"success": True, "output": result.get("output", ""), "task_id": task_id}
            else:
                self.task_manager.update_task(
                    task_id,
                    status="failed",
                    error="Verification failed",
                )
                self._learn_from_result(task, result)
                self.self_improvement.record_error(
                    agent_name, task["description"],
                    result.get("error", "Verification failed")
                )
                return {"success": False, "error": "Verification failed", "task_id": task_id}

        except Exception as e:
            error_msg = str(e)
            log.error(f"Task {task_id} failed: {error_msg}")
            self.task_manager.update_task(task_id, status="failed", error=error_msg)
            self._learn_from_result(task, {"success": False, "error": error_msg})
            self.self_improvement.record_error(agent_name, task["description"], error_msg)
            return {"success": False, "error": error_msg, "task_id": task_id}

    def _verify_result(self, task: dict, result: dict) -> bool:
        """Verify a task result before considering it complete."""
        if not result.get("success", False):
            return False
        # Could add more verification: run tests, check output, etc.
        return True

    def _learn_from_result(self, task: dict, result: dict):
        """Record outcomes in memory for future reference."""
        category = "previous_successes" if result.get("success") else "previous_failures"
        self.memory.store(category, task["id"], {
            "task": task["description"],
            "agent": task.get("required_agent"),
            "result": result.get("output", result.get("error", "")),
        })

    # ─── Autonomy Loop ─────────────────────────────────────────────
    def run_autonomous_loop(self, max_iterations: int = MAX_AUTONOMOUS_ITERATIONS):
        """Process the task queue autonomously."""
        self._running = True
        log.info(f"Autonomous loop starting (max {max_iterations} iterations).")

        for i in range(max_iterations):
            if not self._running:
                log.info("Autonomous loop stopped by user.")
                break

            # Check hardware
            hw = self.hardware.get_status()
            if hw.get("battery_critical") or hw.get("storage_critical"):
                log.warning("Resources critical — pausing autonomous loop.")
                break

            # Get next pending task
            task = self.task_manager.get_next_task()
            if not task:
                log.info("No pending tasks. Autonomous loop complete.")
                break

            log.info(f"Autonomous iteration {i+1}: task {task['id']}")
            self._execute_task(task)

        # Run self-improvement analysis after autonomous cycle
        if self.self_improvement:
            analysis = self.self_improvement.run_analysis()
            if analysis["error_patterns"] or analysis["missing_capabilities"]:
                log.info(f"Self-improvement analysis found {len(analysis['error_patterns'])} "
                         f"error patterns, {len(analysis['missing_capabilities'])} missing capabilities.")

        log.info("Autonomous loop ended.")

    def stop(self):
        """Stop the autonomous loop."""
        self._running = False

    # ─── Status ────────────────────────────────────────────────────
    def status(self) -> dict:
        """Return system status summary."""
        return {
            "agents": list(self.agents.keys()),
            "pending_tasks": self.task_manager.count_tasks("pending") if self.task_manager else 0,
            "completed_tasks": self.task_manager.count_tasks("completed") if self.task_manager else 0,
            "ollama_available": self.ollama.is_available() if self.ollama else False,
            "hardware": self.hardware.get_status() if self.hardware else {},
            "vault": self.vault.get_stats() if self.vault else {},
            "self_improvement": {
                "proposals": len(self.self_improvement.proposals) if self.self_improvement else 0,
                "errors_tracked": len(self.self_improvement.error_patterns) if self.self_improvement else 0,
            } if self.self_improvement else {},
            "running": self._running,
        }
