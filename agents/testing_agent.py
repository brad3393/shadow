"""
TestingAgent — Expert agent for running tests and validating output.
"""
import os
import sys
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

from core.base import BaseAgent
from logging.logger import ShadowLogger

log = ShadowLogger.get("shadow.agents.testing")


class TestingAgent(BaseAgent):
    name: str = "testing_agent"
    description: str = "Runs unit tests, validates code output, and verifies execution results."

    def can_handle(self, task_description: str) -> bool:
        keywords = [
            "test", "validate", "verify", "check result", "pytest",
            "unittest", "assert", "benchmark", "test suite"
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

    def execute(self, task: dict) -> dict:
        desc = task.get("description", task.get("task", ""))
        test_target = task.get("target") or task.get("file_path") or task.get("test_path") or "."
        test_cmd = task.get("command") or task.get("cmd")

        log.info(f"TestingAgent executing: {desc[:80]}")

        guardian = self._get_guardian()
        if guardian:
            allowed, reason = guardian.pre_check("testing_run", {"target": test_target, "command": test_cmd})
            if not allowed:
                return {
                    "success": False,
                    "output": f"Guardian blocked testing execution: {reason}",
                    "error": f"Guardian blocked: {reason}"
                }

        # Determine default command if not specified
        if not test_cmd:
            if os.path.isfile(test_target) and test_target.endswith(".py"):
                test_cmd = f"{sys.executable} -m unittest {test_target}"
            else:
                pytest_res = subprocess.run(["which", "pytest"], capture_output=True, text=True)
                if pytest_res.returncode == 0:
                    test_cmd = f"pytest {test_target}"
                else:
                    test_cmd = f"{sys.executable} -m unittest discover -s {test_target}"

        try:
            res = subprocess.run(
                test_cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=task.get("timeout", 60)
            )
            success = (res.returncode == 0)
            output = res.stdout + ("\n" + res.stderr if res.stderr else "")

            return {
                "success": success,
                "output": output.strip() or f"Test command executed (exit code {res.returncode}).",
                "error": res.stderr.strip() if not success else None,
                "exit_code": res.returncode
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "output": "Test execution timed out after 60 seconds.",
                "error": "TimeoutExpired"
            }
        except Exception as e:
            log.error(f"Testing execution failed: {e}")
            return {
                "success": False,
                "output": f"Testing failed with error: {e}",
                "error": str(e)
            }
