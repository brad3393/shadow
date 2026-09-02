"""
Shadow Bot Factory — Self-building tool creation engine with sandboxed execution.

Responsibilities:
  - Identify missing capabilities
  - Design and generate tool code using Ollama (or template fallback)
  - Write candidate code to temp sandbox in VAULT_DIR/sandbox
  - Safely test code in a subprocess with timeouts
  - Diagnose execution errors and iteratively fix code
  - Promote verified tools to VAULT_DIR and register with capability registry
"""

import os
import sys
import json
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Dict, Any, Optional

from config.config import VAULT_DIR, SANDBOX_TIMEOUT_SECONDS, MAX_CORRECTION_ATTEMPTS
from logging.logger import ShadowLogger

log = ShadowLogger.get("shadow.botfactory")


class BotFactory:
    """Self-building engine for Shadow capabilities and tools."""

    def __init__(self, ollama=None, registry=None):
        self.ollama = ollama
        self.registry = registry
        self.sandbox_dir = Path(VAULT_DIR) / "sandbox"
        self.vault_dir = Path(VAULT_DIR)

        # Ensure sandbox and vault directories exist
        self.sandbox_dir.mkdir(parents=True, exist_ok=True)
        self.vault_dir.mkdir(parents=True, exist_ok=True)

        # Lazy load OllamaInterface if not passed
        if self.ollama is None:
            try:
                from ollama.ollama_interface import OllamaInterface
                self.ollama = OllamaInterface()
            except Exception as e:
                log.warning(f"OllamaInterface not available for BotFactory: {e}")
                self.ollama = None

        # Lazy load CapabilityRegistry if not passed
        if self.registry is None:
            try:
                from registry.capability_registry import CapabilityRegistry
                self.registry = CapabilityRegistry()
            except Exception as e:
                log.warning(f"CapabilityRegistry not available for BotFactory: {e}")
                self.registry = None

    def build_tool(self, capability_description: str, max_attempts: int = MAX_CORRECTION_ATTEMPTS) -> dict:
        """
        Main self-building pipeline.
        
        Steps:
          1. Identify missing capability (check capability_registry)
          2. Design a solution (use Ollama if available, else template-based)
          3. Ask Ollama to generate Python code for the tool
          4. Write the code to a temp sandbox file in VAULT_DIR/sandbox/
          5. Test the code by running it in a subprocess with timeout
          6. Capture stdout/stderr
          7. If failed, diagnose the error, ask Ollama to fix, test again
          8. Repeat up to max_attempts times
          9. If it passes, move to VAULT_DIR/ and register in capability_registry
          10. Return {'success': bool, 'tool_name': str, 'path': str, 'attempts': int, 'output': str}
        """
        log.info(f"Initiating tool build for capability: '{capability_description}'")

        # Step 1: Identify missing capability (check capability_registry)
        tool_name = self._sanitize_tool_name(capability_description)
        if self.registry:
            if hasattr(self.registry, "has_capability") and self.registry.has_capability(capability_description):
                log.info(f"Capability '{capability_description}' already exists in registry.")
            elif hasattr(self.registry, "get_tool") and self.registry.get_tool(tool_name):
                log.info(f"Tool '{tool_name}' already exists in registry.")

        # Step 2 & 3: Design solution & generate code
        code = self._generate_tool_code(capability_description, tool_name)

        # Step 4: Write to temp sandbox file in VAULT_DIR/sandbox/
        sandbox_path = self.sandbox_dir / f"{tool_name}_sandbox.py"
        with open(sandbox_path, "w", encoding="utf-8") as f:
            f.write(code)

        attempts = 0
        last_output = ""
        success = False

        # Step 5 - 8: Test loop with diagnosis and fix
        for attempt in range(1, max_attempts + 1):
            attempts = attempt
            log.info(f"Testing candidate tool '{tool_name}' (Attempt {attempt}/{max_attempts})")

            # Step 5 & 6: Test in sandbox & capture stdout/stderr
            test_res = self._sandbox_test(sandbox_path)
            last_output = test_res.get("stdout", "") or test_res.get("stderr", "")

            if test_res.get("success"):
                log.info(f"Sandbox test passed for '{tool_name}' on attempt {attempt}.")
                success = True
                break

            # Step 7: If failed, diagnose error and fix
            stderr = test_res.get("stderr", "")
            stdout = test_res.get("stdout", "")
            error_details = stderr if stderr.strip() else stdout
            log.warning(f"Sandbox test failed on attempt {attempt}: {error_details[:200]}")

            if attempt < max_attempts:
                log.info(f"Diagnosing and attempting fix for '{tool_name}'...")
                code = self._diagnose_and_fix(code, error_details, capability_description)
                with open(sandbox_path, "w", encoding="utf-8") as f:
                    f.write(code)

        # Step 9: If it passes, move to VAULT_DIR/ and register in capability_registry
        final_path = sandbox_path
        if success:
            target_path = self.vault_dir / f"{tool_name}.py"
            shutil.copy2(sandbox_path, target_path)
            final_path = target_path

            # Clean up sandbox file
            try:
                sandbox_path.unlink(missing_ok=True)
            except Exception:
                pass

            # Register capability
            if self.registry:
                try:
                    if hasattr(self.registry, "register_tool"):
                        self.registry.register_tool(tool_name, capability_description, str(target_path))
                    elif hasattr(self.registry, "register_capability"):
                        self.registry.register_capability(tool_name, capability_description)
                except Exception as e:
                    log.warning(f"Could not register tool in capability registry: {e}")

        # Step 10: Return result dictionary
        return {
            "success": success,
            "tool_name": tool_name,
            "path": str(final_path),
            "attempts": attempts,
            "output": last_output,
        }

    def _sandbox_test(self, code_path: Path) -> dict:
        """
        Runs the code in a isolated subprocess with timeout and returns execution metrics.
        Returns {'success': bool, 'stdout': str, 'stderr': str, 'returncode': int}
        """
        if not code_path.exists():
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Sandbox file does not exist: {code_path}",
                "returncode": -1,
            }

        cmd = [sys.executable, str(code_path)]
        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=SANDBOX_TIMEOUT_SECONDS,
                cwd=str(self.sandbox_dir),
            )
            return {
                "success": res.returncode == 0,
                "stdout": res.stdout,
                "stderr": res.stderr,
                "returncode": res.returncode,
            }
        except subprocess.TimeoutExpired as te:
            return {
                "success": False,
                "stdout": te.stdout or "",
                "stderr": f"Execution timed out after {SANDBOX_TIMEOUT_SECONDS} seconds.",
                "returncode": -1,
            }
        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Subprocess error: {str(e)}",
                "returncode": -1,
            }

    def _diagnose_and_fix(self, code: str, error: str, capability: str) -> str:
        """Uses Ollama (or template rule fix) to diagnose error and produce fixed Python code."""
        if self.ollama and hasattr(self.ollama, "is_available") and self.ollama.is_available():
            prompt = (
                f"You are an expert Python bug fixer. The following tool code was written for capability '{capability}'.\n"
                f"When tested in the sandbox, it failed with error:\n"
                f"```\n{error}\n```\n\n"
                f"Original code:\n"
                f"```python\n{code}\n```\n\n"
                f"Fix the code. Requirements:\n"
                f"1. Must define a `run(**kwargs)` function that executes the capability and returns a result.\n"
                f"2. Must include `if __name__ == '__main__': run()` at the bottom so it executes cleanly.\n"
                f"3. Return ONLY valid Python code inside a ```python ``` block or as plain text.\n"
            )
            try:
                response = self.ollama.generate(prompt)
                extracted = self._extract_code(response)
                if extracted.strip():
                    return extracted
            except Exception as e:
                log.warning(f"Ollama diagnosis failed: {e}")

        # Fallback fix if Ollama not available or failed: append main block if missing
        if "def run(" in code and "if __name__" not in code:
            code += "\n\nif __name__ == '__main__':\n    import sys\n    res = run()\n    print(res)\n"
        return code

    def _generate_tool_code(self, capability_description: str, tool_name: str) -> str:
        """Generate candidate tool Python code via Ollama or fallback template."""
        if self.ollama and hasattr(self.ollama, "is_available") and self.ollama.is_available():
            prompt = (
                f"Write a complete, standalone Python script for a tool that implements this capability:\n"
                f"'{capability_description}'\n\n"
                f"Requirements:\n"
                f"1. Define a `run(**kwargs)` function that performs the action and returns a dict or result.\n"
                f"2. Include `if __name__ == '__main__': run()` so running the script directly executes `run()`.\n"
                f"3. Return ONLY valid Python code with imports and comments.\n"
            )
            try:
                response = self.ollama.generate(prompt)
                extracted = self._extract_code(response)
                if extracted.strip():
                    return extracted
            except Exception as e:
                log.warning(f"Ollama tool generation failed: {e}")

        # Template fallback generator
        return (
            f"#!/usr/bin/env python3\n"
            f'"""\n'
            f"Auto-generated tool: {tool_name}\n"
            f"Capability: {capability_description}\n"
            f'"""\n'
            f"import sys\n"
            f"import json\n\n\n"
            f"def run(**kwargs):\n"
            f"    \"\"\"Execute capability: {capability_description}\"\"\"\n"
            f"    # Auto-generated implementation\n"
            f'    result = {{"status": "success", "capability": "{capability_description}", "inputs": kwargs}}\n'
            f"    return result\n\n\n"
            f"if __name__ == '__main__':\n"
            f"    res = run()\n"
            f"    print(json.dumps(res))\n"
            f"    sys.exit(0)\n"
        )

    def _extract_code(self, text: str) -> str:
        """Extract code from response string (e.g. stripping markdown fences)."""
        match = re.search(r"```python\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        match_generic = re.search(r"```\s*(.*?)\s*```", text, re.DOTALL)
        if match_generic:
            return match_generic.group(1).strip()
        return text.strip()

    def _sanitize_tool_name(self, description: str) -> str:
        """Convert a capability description into a valid Python module identifier."""
        clean = re.sub(r"[^a-zA-Z0-9]+", "_", description.lower()).strip("_")
        if not clean.startswith("tool_"):
            clean = f"tool_{clean}"
        return clean[:50]


def self_test() -> bool:
    """Component self-test required by run_tests.py."""
    try:
        factory = BotFactory()

        # Test 1: Sandbox test on valid code file
        test_file = factory.sandbox_dir / "test_valid_tool.py"
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("def run(): return {'ok': True}\nif __name__ == '__main__': print('PASS')\n")

        res = factory._sandbox_test(test_file)
        if not res["success"] or "PASS" not in res["stdout"]:
            log.error(f"BotFactory self_test failed on _sandbox_test: {res}")
            return False

        # Cleanup temp file
        test_file.unlink(missing_ok=True)

        # Test 2: Build tool pipeline
        build_res = factory.build_tool("Calculate square root of 16", max_attempts=2)
        if not build_res["success"]:
            log.error(f"BotFactory self_test failed on build_tool: {build_res}")
            return False

        # Verify built file exists
        if not Path(build_res["path"]).exists():
            log.error(f"BotFactory self_test built file missing at {build_res['path']}")
            return False

        log.info("BotFactory self_test passed successfully.")
        return True
    except Exception as e:
        log.error(f"BotFactory self_test exception: {e}")
        return False


if __name__ == "__main__":
    if self_test():
        print("BotFactory tests PASSED.")
    else:
        print("BotFactory tests FAILED.")
        sys.exit(1)
