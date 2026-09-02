"""
Shadow CLI — Interactive REPL interface.

Features:
  - Boot Shadow Core with all agents
  - Type commands in natural language, Shadow routes to the right agent
  - Slash commands for system control:
      /status    — show system status
      /agents    — list registered agents
      /tasks     — show task queue
      /memory    — search memory
      /hardware  — show hardware status
      /autonomous — run the autonomous task loop
      /help      — show available commands
      /quit      — exit Shadow
  - Tab-completion for slash commands (if readline is available)
"""
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.shadow_core import ShadowCore
from logging.logger import ShadowLogger
from config.config import SHADOW_ROOT

log = ShadowLogger.get("shadow.ui.cli")

# ANSI colors
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RESET  = "\033[0m"

BANNER = r"""
  ███████  █████  ███   ██ ██   ██
  ██      ██   ██ ████  ██ ██  ██
  ███████ ███████ ██ ██ ██ █████
       ██ ██   ██ ██  ██ ██ ██
  ███████ ██   ██ ██   ██ ██ ██
"""


class ShadowCLI:
    """Interactive command-line interface for Shadow."""

    SLASH_COMMANDS = [
        "/status", "/agents", "/tasks", "/memory", "/hardware",
        "/autonomous", "/help", "/quit", "/restart", "/clear",
    ]

    def __init__(self):
        self.core = ShadowCore()
        self._running = False

    def run(self):
        """Start the interactive REPL."""
        print(f"{CYAN}{BANNER}{RESET}")
        print(f"  {BOLD}Shadow — Autonomous Modular AI Network{RESET}")
        print(f"  {DIM}Type /help for commands, or just talk to me.{RESET}")
        print()

        # Boot the core
        print(f"{DIM}Booting Shadow Core...{RESET}", end=" ", flush=True)
        try:
            self.core.boot()
            print(f"{GREEN}OK{RESET}")
            ollama_status = "online" if self.core.ollama and self.core.ollama.is_available() else f"{YELLOW}offline{RESET}"
            agent_count = len(self.core.agents)
            print(f"  Agents: {GREEN}{agent_count}{RESET}  |  Ollama: {ollama_status}")
            print()
        except Exception as e:
            print(f"{RED}FAILED{RESET}")
            print(f"  Error: {e}")
            sys.exit(1)

        # Setup readline tab-completion if available
        try:
            import readline
            readline.set_completer(self._completer)
            readline.parse_and_bind("tab: complete")
        except ImportError:
            pass

        self._running = True
        self._loop()

    def _loop(self):
        """Main REPL loop."""
        while self._running:
            try:
                user_input = input(f"{CYAN}shadow>{RESET} ").strip()
            except EOFError:
                print("\nBye.")
                break
            except KeyboardInterrupt:
                print(f"\n{YELLOW}(Use /quit to exit){RESET}")
                continue

            if not user_input:
                continue

            if user_input.startswith("/"):
                self._handle_slash(user_input)
            else:
                self._handle_command(user_input)

    def _handle_slash(self, command: str):
        """Handle slash commands."""
        cmd = command.lower().strip()

        if cmd in ("/quit", "/exit", "/q"):
            self._running = False
            self.core.stop()
            print(f"{DIM}Shutting down Shadow...{RESET}")
            return

        if cmd == "/help":
            self._print_help()
            return

        if cmd == "/status":
            self._print_status()
            return

        if cmd == "/agents":
            self._print_agents()
            return

        if cmd == "/tasks":
            self._print_tasks()
            return

        if cmd == "/memory":
            print(f"{YELLOW}Usage: /memory <category> [query]{RESET}")
            print(f"{DIM}Categories: user_info, instructions, projects, tasks, knowledge, "
                  f"learned_procedures, tool_descriptions, agent_capabilities, "
                  f"previous_successes, previous_failures{RESET}")
            return

        if cmd.startswith("/memory "):
            parts = command.split(None, 2)
            category = parts[1] if len(parts) > 1 else ""
            query = parts[2] if len(parts) > 2 else None
            self._search_memory(category, query)
            return

        if cmd == "/hardware":
            self._print_hardware()
            return

        if cmd == "/autonomous":
            self._run_autonomous()
            return

        if cmd == "/clear":
            os.system("clear" if os.name != "nt" else "cls")
            return

        if cmd == "/restart":
            print(f"{DIM}Restarting Shadow Core...{RESET}")
            self.core = ShadowCore()
            self.core.boot()
            print(f"{GREEN}Core restarted.{RESET}")
            return

        print(f"{RED}Unknown command: {command}{RESET}  {DIM}Type /help for available commands.{RESET}")

    def _handle_command(self, user_input: str):
        """Send a natural-language command to the Core."""
        print(f"{DIM}→ Processing...{RESET}")
        try:
            result = self.core.receive_command(user_input)
            print()
            if result.get("success"):
                output = result.get("output", "")
                if output:
                    print(f"{GREEN}✓{RESET} {output}")
                else:
                    print(f"{GREEN}✓ Done.{RESET}")
            elif result.get("paused"):
                print(f"{YELLOW}⚠ {result.get('output', 'Paused')}{RESET}")
            else:
                print(f"{RED}✗ {result.get('error', result.get('output', 'Failed'))}{RESET}")
            print()
        except Exception as e:
            print(f"{RED}✗ Error: {e}{RESET}\n")

    def _print_help(self):
        print(f"\n{BOLD}Shadow Commands:{RESET}")
        print(f"  {CYAN}/status{RESET}      Show system status (agents, tasks, hardware, Ollama)")
        print(f"  {CYAN}/agents{RESET}      List all registered expert agents")
        print(f"  {CYAN}/tasks{RESET}       Show task queue (pending, in-progress, completed)")
        print(f"  {CYAN}/memory{RESET}      Search memory: {DIM}/memory <category> [query]{RESET}")
        print(f"  {CYAN}/hardware{RESET}    Show hardware monitor readings (CPU, RAM, battery, storage)")
        print(f"  {CYAN}/autonomous{RESET}  Run the autonomous task loop")
        print(f"  {CYAN}/restart{RESET}     Restart Shadow Core (re-init all subsystems)")
        print(f"  {CYAN}/clear{RESET}       Clear the terminal screen")
        print(f"  {CYAN}/quit{RESET}        Exit Shadow")
        print(f"\n{BOLD}Or just type a natural-language command:{RESET}")
        print(f"  {DIM}shadow> check system uptime{RESET}")
        print(f"  {DIM}shadow> write a script that prints hello world{RESET}")
        print(f"  {DIM}shadow> list all Python files in the current directory{RESET}")
        print(f"  {DIM}shadow> scan for security issues in this directory{RESET}")
        print()

    def _print_status(self):
        status = self.core.status()
        print(f"\n{BOLD}Shadow Status{RESET}")
        print(f"  Agents:          {GREEN}{len(status['agents'])}{RESET}")
        print(f"  Pending tasks:   {status.get('pending_tasks', 0)}")
        print(f"  Completed tasks: {status.get('completed_tasks', 0)}")
        print(f"  Ollama:          {GREEN if status.get('ollama_available') else RED}{'online' if status.get('ollama_available') else 'offline'}{RESET}")
        print(f"  Autonomous:      {GREEN}running{RESET if status.get('running') else f'{YELLOW}idle{RESET}'}")
        print()

    def _print_agents(self):
        print(f"\n{BOLD}Expert Agents ({len(self.core.agents)}):{RESET}")
        for name, agent in self.core.agents.items():
            print(f"  {CYAN}{name:25}{RESET} {agent.description}")
        print()

    def _print_tasks(self):
        if not self.core.task_manager:
            print(f"{RED}Task manager not initialized.{RESET}")
            return
        tasks = self.core.task_manager.list_tasks()
        if not tasks:
            print(f"{DIM}No tasks in queue.{RESET}")
            return
        print(f"\n{BOLD}Task Queue ({len(tasks)}):{RESET}")
        for t in tasks[:20]:
            status_color = GREEN if t.get("status") == "completed" else (YELLOW if t.get("status") == "in_progress" else DIM)
            print(f"  [{status_color}{t.get('status', '?'):12}{RESET}] {t.get('id', '?')[:8]}  {t.get('description', '')[:60]}")
        if len(tasks) > 20:
            print(f"  {DIM}... and {len(tasks) - 20} more{RESET}")
        print()

    def _search_memory(self, category: str, query: str = None):
        if not self.core.memory:
            print(f"{RED}Memory system not initialized.{RESET}")
            return
        if query:
            results = self.core.memory.search(category, query)
        else:
            results = self.core.memory.list_category(category)
        if not results:
            print(f"{DIM}No memories found in '{category}'.{RESET}")
            return
        print(f"\n{BOLD}Memory: {category} ({len(results)} entries){RESET}")
        for entry in results[:20]:
            key = entry.get("key", "?")
            value = entry.get("value", "")
            if isinstance(value, dict) or isinstance(value, list):
                value = json.dumps(value)[:80]
            print(f"  {CYAN}{key:20}{RESET} {str(value)[:80]}")
        print()

    def _print_hardware(self):
        if not self.core.hardware:
            print(f"{RED}Hardware monitor not initialized.{RESET}")
            return
        hw = self.core.hardware.get_status()
        print(f"\n{BOLD}Hardware Status{RESET}")
        print(f"  CPU usage:    {self._bar(hw.get('cpu_pct', 0))}")
        print(f"  RAM usage:    {self._bar(hw.get('ram_pct', 0))}")
        print(f"  RAM total:    {hw.get('ram_total_gb', '?')} GB")
        print(f"  Storage free: {hw.get('storage_free_pct', '?')}%")
        print(f"  Battery:      {hw.get('battery_pct', 'N/A')}")
        print(f"  Network:      {GREEN if hw.get('network_connected') else RED}{'connected' if hw.get('network_connected') else 'disconnected'}{RESET}")
        print()

    def _run_autonomous(self):
        print(f"{DIM}Starting autonomous task loop... (Ctrl+C to stop){RESET}")
        try:
            self.core.run_autonomous_loop()
        except KeyboardInterrupt:
            self.core.stop()
            print(f"\n{YELLOW}Autonomous loop stopped.{RESET}")

    def _completer(self, text, state):
        """Tab-completion for slash commands."""
        matches = [cmd for cmd in self.SLASH_COMMANDS if cmd.startswith(text)]
        if state < len(matches):
            return matches[state]
        return None
