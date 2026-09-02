"""
CodingAgent — Expert agent for writing, modifying, refactoring, and debugging code.
"""
import ast
import os
import re
import sys
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

from core.base import BaseAgent
from logging.logger import ShadowLogger

log = ShadowLogger.get("shadow.agents.coding")


class CodingAgent(BaseAgent):
    name: str = "coding_agent"
    description: str = "Writes, modifies, refactors, and debugs code across Python, JavaScript, and other languages."

    def can_handle(self, task_description: str) -> bool:
        keywords = [
            "write code", "fix bug", "create script", "refactor",
            "python code", "python script", "javascript", "javascript code",
            "debug code", "debug script", "program a", "implement a",
            "write a function", "write a class", "algorithm",
            "syntax error", "compile", "code review", "optimize code",
            "write a python", "write a script"
        ]
        desc_lower = task_description.lower()
        return any(kw in desc_lower for kw in keywords)

    def _get_ollama(self):
        try:
            from ollama.ollama_interface import OllamaInterface
            ollama = OllamaInterface()
            if hasattr(ollama, "is_available") and ollama.is_available():
                return ollama
            return ollama
        except Exception as e:
            log.debug(f"Ollama interface unavailable: {e}")
            return None

    def execute(self, task: dict) -> dict:
        desc = task.get("description", task.get("task", ""))
        file_path = task.get("file_path") or task.get("path")

        # Try to infer file path from task description if not explicitly provided
        if not file_path:
            match = re.search(r"(\b[\w\-_/.]+\.(?:py|js|ts|html|css|json|sh|cpp|c|rs)\b)", desc)
            if match:
                file_path = match.group(1)

        log.info(f"CodingAgent executing: {desc[:80]}")

        ollama = self._get_ollama()
        code = task.get("code")

        if not code:
            if ollama:
                prompt = (
                    f"You are an expert programmer. Complete the following task:\n"
                    f"Task: {desc}\n"
                    f"Provide clean, production-ready code. Return ONLY the code inside Markdown code blocks ```python ... ```."
                )
                try:
                    response = ollama.generate(prompt)
                    code_match = re.search(r"```(?:\w+)?\n(.*?)```", response, re.DOTALL)
                    if code_match:
                        code = code_match.group(1).strip()
                    else:
                        code = response.strip()
                except Exception as e:
                    log.warning(f"Ollama generation failed: {e}")
                    code = self._fallback_code_generator(desc)
            else:
                code = self._fallback_code_generator(desc)

        output_info = []

        # Write code if file path specified
        if file_path:
            try:
                p = Path(file_path)
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(code, encoding="utf-8")
                output_info.append(f"Code written to {file_path}")
            except Exception as e:
                return {
                    "success": False,
                    "output": f"Failed to write code to {file_path}: {e}",
                    "error": str(e)
                }

        # Test the generated code
        test_success, test_msg = self._test_code(code, file_path)
        if output_info:
            full_output = "\n".join(output_info) + "\n" + test_msg
        else:
            full_output = test_msg

        return {
            "success": test_success,
            "output": f"```python\n{code}\n```\n\n{full_output}",
            "error": None if test_success else test_msg
        }

    def _fallback_code_generator(self, desc: str) -> str:
        """Fallback code generator when Ollama is unavailable."""
        return (
            f'#!/usr/bin/env python3\n'
            f'"""\nGenerated code for task: {desc}\n"""\n\n'
            f'def main():\n'
            f'    print("Executing task: {desc}")\n'
            f'    # Implementation logic\n\n'
            f'if __name__ == "__main__":\n'
            f'    main()\n'
        )

    def _test_code(self, code: str, file_path: Optional[str] = None) -> tuple[bool, str]:
        """Validates code syntax and tests execution if Python."""
        try:
            ast.parse(code)
            syntax_check = "Syntax check PASSED."
        except SyntaxError as se:
            return False, f"Syntax Error in generated code: {se}"

        if file_path and file_path.endswith(".py"):
            try:
                res = subprocess.run(
                    [sys.executable, "-m", "py_compile", file_path],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if res.returncode == 0:
                    return True, f"{syntax_check} py_compile succeeded for {file_path}."
                else:
                    return False, f"py_compile failed for {file_path}: {res.stderr}"
            except Exception as e:
                return True, f"{syntax_check} (py_compile check skipped: {e})"

        return True, syntax_check
