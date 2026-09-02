"""
SystemAgent — Expert agent for running system commands and managing processes safely.

Translates natural-language requests into actual shell commands before executing.
When Ollama is available, uses LLM for translation. When offline, uses a built-in
keyword-to-command mapping for common system operations.
"""
import os
import subprocess
import shlex
import re
from pathlib import Path
from typing import Dict, Any, Optional

from core.base import BaseAgent
from logging.logger import ShadowLogger
from config.config import SANDBOX_TIMEOUT_SECONDS

log = ShadowLogger.get("shadow.agents.system")


# ─── Offline command translation table ──────────────────────────────
# Maps natural-language patterns to real shell commands.
# Each entry: (regex_pattern, command_template)
# {input} in the template is replaced with extracted text from the user's request.
COMMAND_MAP = [
    # ── System info ──
    (r"(show|check|get|display).*(uptime|how long.*up)", "uptime"),
    (r"(show|check|get|display|what).*\b(os|operating system|version|kernel)\b", "uname -a"),
    (r"(show|check|get|display).*(hostname|host name|machine name)", "hostname"),
    (r"(show|list|get).*(processes|running processes|all processes)", "ps aux"),
    (r"(show|check|get).*(disk|storage|drive).*(usage|space|info)", "df -h"),
    (r"(show|check|get).*(memory|ram).*(usage|info|free|available)", "free -h"),
    (r"(show|check|get).*(cpu|processor).*(usage|info|load)", "top -bn1 | head -5"),
    (r"(show|check|get).*(ip|network|interface|address|config)", "ip addr 2>/dev/null || ifconfig 2>/dev/null"),
    (r"(show|check|get).*(port|ports|listening|open connections)", "ss -tlnp 2>/dev/null || netstat -tlnp 2>/dev/null"),
    (r"(show|check|get).*(environment|env|variables)", "env | sort"),
    (r"(who|which|list).*(user|users|logged in|sessions)", "who"),
    (r"(show|check|get).*(date|time)", "date"),

    # ── File system ──
    (r"(list|show|display).*(files|directory|dir|contents).*(in|from|of)\s+(.+)", "ls -la {path}"),
    (r"(list|show|display).*(files|directory|dir|contents)", "ls -la"),
    (r"(find|search).*(for\s+)?(.+?)\s+(in|under|within)\s+(.+)", "find {path} -name '*{pattern}*' 2>/dev/null"),
    (r"(find|search).*(for\s+)?python\s+files", "find . -name '*.py' -type f 2>/dev/null"),

    # ── Process management ──
    (r"(kill|stop|terminate)\s+(process|pid)?\s*(\d+)", "kill {pid}"),
    (r"(kill|stop|terminate)\s+(process|pid)?\s+named\s+(\S+)", "pkill {name}"),

    # ── Service management ──
    (r"(start|stop|restart|status).*(service|daemon)\s+(\S+)", "systemctl {action} {service} 2>/dev/null || service {service} {action}"),
    (r"(list|show).*(services|daemons)", "systemctl list-units --type=service --state=running 2>/dev/null || service --status-all 2>/dev/null"),

    # ── Network ──
    (r"(ping|check connection)\s+(\S+)", "ping -c 4 {host}"),
    (r"(check|test).*(internet|connection|connectivity)", "ping -c 1 8.8.8.8 2>/dev/null && echo 'Internet OK' || echo 'No internet'"),

    # ── System update / package ──
    (r"(check|show|list).*(installed|packages|software)", "dpkg -l 2>/dev/null | tail -20 || pip list 2>/dev/null"),
    (r"(show|check).*(python|pip).*(version|info)", "python3 --version && pip3 --version 2>/dev/null"),
]


class SystemAgent(BaseAgent):
    name: str = "system_agent"
    description: str = "Runs system commands and manages system processes safely."

    def can_handle(self, task_description: str) -> bool:
        keywords = [
            "system", "process", "shell", "run command", "kill", "service",
            "bash", "terminal", "exec", "command", "ps", "uptime",
            "disk", "memory", "ram", "cpu", "network", "ping", "hostname",
            "os version", "kernel", "ip address", "port", "env",
            "date", "time", "who", "installed", "packages", "python version",
            "storage", "drive", "temperature", "load", "users", "sessions",
        ]
        desc_lower = task_description.lower()
        return any(kw in desc_lower for kw in keywords)

    def _get_guardian(self):
        try:
            from guardian.guardian import Guardian
            return Guardian()
        except Exception as e:
            log.debug(f"Guardian unavailable: {e}")
            return None

    def _translate_command(self, description: str) -> str:
        """
        Translate a natural-language description into a shell command.
        Uses Ollama if available, otherwise falls back to the keyword mapping.
        """
        desc = description.strip()
        desc_lower = desc.lower()

        # If it already looks like a raw command (starts with a known binary), pass through
        raw_prefixes = ["ls ", "ps ", "df ", "free ", "uptime", "uname", "hostname", "cat ",
                        "echo ", "pwd", "who", "date", "top ", "kill ", "pkill ", "ping ",
                        "find ", "grep ", "head ", "tail ", "wc ", "du ", "env", "ip ",
                        "ss ", "netstat", "systemctl ", "service ", "dpkg ", "pip ", "python"]
        for prefix in raw_prefixes:
            if desc_lower.startswith(prefix):
                return desc

        # If prefixed with explicit "run command:" or "exec:", extract
        if desc_lower.startswith("run command:") or desc_lower.startswith("exec:") or desc_lower.startswith("run:"):
            cmd = desc.split(":", 1)[1].strip()
            return cmd

        # ── Offline translation via keyword map ──
        for pattern, template in COMMAND_MAP:
            match = re.search(pattern, desc_lower)
            if match:
                cmd = template
                # Extract path from group
                groups = match.groups()
                if "{path}" in cmd and len(groups) >= 4:
                    cmd = cmd.replace("{path}", shlex.quote(groups[-1].strip()))
                elif "{path}" in cmd and len(groups) >= 1:
                    cmd = cmd.replace("{path}", shlex.quote(groups[-1].strip()))
                if "{pattern}" in cmd and len(groups) >= 3:
                    cmd = cmd.replace("{pattern}", groups[1].strip() if groups[1] else groups[0].strip())
                if "{pid}" in cmd and len(groups) >= 3:
                    cmd = cmd.replace("{pid}", groups[2])
                if "{name}" in cmd and len(groups) >= 3:
                    cmd = cmd.replace("{name}", groups[2])
                if "{action}" in cmd and len(groups) >= 3:
                    cmd = cmd.replace("{action}", groups[0])
                if "{service}" in cmd and len(groups) >= 3:
                    cmd = cmd.replace("{service}", groups[2])
                if "{host}" in cmd and len(groups) >= 2:
                    cmd = cmd.replace("{host}", groups[1])
                return cmd

        # ── Ollama-based translation ──
        try:
            from ollama.ollama_interface import OllamaInterface
            ollama = OllamaInterface()
            if ollama.is_available():
                prompt = (
                    f"Translate this natural-language request into a single safe shell command. "
                    f"Return ONLY the command, nothing else.\n"
                    f"Request: {desc}"
                )
                response = ollama.generate(prompt).strip()
                if response and not response.startswith("Sorry") and len(response) < 200:
                    return response
        except Exception as e:
            log.debug(f"Ollama translation failed: {e}")

        # ── Last resort: pass through as-is (user may have typed a real command) ──
        log.warning(f"Could not translate '{desc[:60]}' — passing through as raw command")
        return desc

    def execute(self, task: dict) -> dict:
        desc = task.get("description", task.get("task", ""))
        command = task.get("command") or task.get("cmd")

        log.info(f"SystemAgent executing: {desc[:80]}")

        # Translate natural language to shell command
        if not command:
            command = self._translate_command(desc)

        log.info(f"Translated command: {command[:120]}")

        # ── Safety: block catastrophic commands ──
        forbidden = ["rm -rf /", ":(){ :|:& };:", "mkfs", "dd if=/dev/zero", "shutdown", "reboot"]
        if any(f in command for f in forbidden):
            return {
                "success": False,
                "output": f"Command blocked due to catastrophic system safety risk: {command}",
                "error": "Forbidden command"
            }

        # ── Guardian pre-check ──
        guardian = self._get_guardian()
        if guardian:
            allowed, reason = guardian.pre_check("system_command", {"command": command})
            if not allowed:
                return {
                    "success": False,
                    "output": f"Guardian blocked command execution: {reason}",
                    "error": f"Guardian blocked: {reason}"
                }

        # ── Execute ──
        try:
            res = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=task.get("timeout", SANDBOX_TIMEOUT_SECONDS)
            )
            success = (res.returncode == 0)
            output = res.stdout if success else res.stdout + "\n" + res.stderr
            return {
                "success": success,
                "output": output.strip() or "Command completed with no output.",
                "error": res.stderr.strip() if not success else None,
                "exit_code": res.returncode,
                "command": command,
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "output": f"Command timed out after {SANDBOX_TIMEOUT_SECONDS} seconds.",
                "error": "TimeoutExpired",
                "command": command,
            }
        except Exception as e:
            log.error(f"System command execution error: {e}")
            return {
                "success": False,
                "output": f"Execution error: {e}",
                "error": str(e),
                "command": command,
            }
