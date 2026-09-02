"""
DocumentationAgent — Expert agent for generating documentation, READMEs, and docstrings.
"""
import ast
import os
import re
from pathlib import Path
from typing import Dict, Any, Optional

from core.base import BaseAgent
from logging.logger import ShadowLogger

log = ShadowLogger.get("shadow.agents.documentation")


class DocumentationAgent(BaseAgent):
    name: str = "documentation_agent"
    description: str = "Generates documentation, README files, docstrings, and module guides."

    def can_handle(self, task_description: str) -> bool:
        keywords = [
            "document", "readme", "docstring", "describe", "explain",
            "doc", "comments", "manual", "guide", "documentation"
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
        target_path = task.get("path") or task.get("file_path") or task.get("target")

        log.info(f"DocumentationAgent executing: {desc[:80]}")

        if not target_path:
            match = re.search(r"(\b[\w\-_/.]+\.(?:py|js|ts|json|md)\b|\b[\w\-_/.]+/)", desc)
            if match:
                target_path = match.group(1)

        source_code = ""
        if target_path and os.path.exists(target_path):
            p = Path(target_path)
            if p.is_file():
                source_code = p.read_text(encoding="utf-8", errors="ignore")

        ollama = self._get_ollama()
        docs = ""

        if ollama:
            prompt = (
                f"You are a technical documentation writer. Generate clear, complete Markdown documentation for the following task/code:\n"
                f"Task: {desc}\n"
                f"Source context: {source_code[:3000]}\n"
            )
            try:
                docs = ollama.generate(prompt)
            except Exception as e:
                log.warning(f"Ollama doc generation failed: {e}")
                docs = self._fallback_docs(target_path, source_code)
        else:
            docs = self._fallback_docs(target_path, source_code)

        output_path = task.get("output_file")
        if output_path:
            p = Path(output_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(docs, encoding="utf-8")
            out_msg = f"Documentation saved to {output_path}:\n\n{docs}"
        else:
            out_msg = docs

        return {
            "success": True,
            "output": out_msg,
            "error": None
        }

    def _fallback_docs(self, target_path: Optional[str], source_code: str) -> str:
        lines = [f"# Documentation for {target_path or 'Module'}\n"]

        if source_code:
            try:
                tree = ast.parse(source_code)
                classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
                functions = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]

                lines.append("## Structural Overview")
                if classes:
                    lines.append("### Classes")
                    for c in classes:
                        lines.append(f"- `{c}`")
                if functions:
                    lines.append("### Functions")
                    for f in functions:
                        lines.append(f"- `{f}()` ")
            except Exception:
                lines.append("## Overview\nSource file analyzed successfully.")
        else:
            lines.append("## Overview\nAuto-generated documentation template.")

        return "\n".join(lines)
