"""
LearningAgent — Expert agent for ingesting documents, extracting knowledge, and studying content.
"""
import os
import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional

from core.base import BaseAgent
from logging.logger import ShadowLogger
from config.config import KNOWLEDGE_DIR

log = ShadowLogger.get("shadow.agents.learning")


class LearningAgent(BaseAgent):
    name: str = "learning_agent"
    description: str = "Ingests documents, extracts knowledge, and summarizes insights into the knowledge base."

    def can_handle(self, task_description: str) -> bool:
        keywords = [
            "learn", "ingest", "read document", "study", "extract knowledge",
            "knowledge", "insights", "learnings", "extract insights",
            "extract key", "extract facts", "key facts", "extract information",
            "summarize document", "index document", "read pdf", "read manual"
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
        doc_path = task.get("file_path") or task.get("path") or task.get("document")

        log.info(f"LearningAgent executing: {desc[:80]}")

        if not doc_path:
            match = re.search(r"(\b[\w\-_/.]+\.(?:txt|md|pdf|doc|docx|json|py)\b)", desc)
            if match:
                doc_path = match.group(1)

        content = ""
        if doc_path and os.path.exists(doc_path):
            try:
                content = Path(doc_path).read_text(encoding="utf-8", errors="ignore")
            except Exception as e:
                return {
                    "success": False,
                    "output": f"Failed to read document at {doc_path}: {e}",
                    "error": str(e)
                }
        else:
            content = task.get("text", desc)

        ollama = self._get_ollama()
        summary = ""

        if ollama:
            prompt = (
                f"You are a knowledge extraction agent. Analyze the following document and extract key concepts, "
                f"definitions, and actionable insights as bullet points:\n\n"
                f"Document:\n{content[:4000]}\n"
            )
            try:
                summary = ollama.generate(prompt)
            except Exception as e:
                log.warning(f"Ollama knowledge extraction failed: {e}")
                summary = self._fallback_extraction(content)
        else:
            summary = self._fallback_extraction(content)

        save_file = task.get("save_as")
        if save_file:
            target_file = KNOWLEDGE_DIR / save_file
            target_file.parent.mkdir(parents=True, exist_ok=True)
            target_file.write_text(summary, encoding="utf-8")
            output_msg = f"Knowledge extracted and saved to {target_file}:\n\n{summary}"
        else:
            output_msg = f"Knowledge extracted:\n\n{summary}"

        return {
            "success": True,
            "output": output_msg,
            "error": None
        }

    def _fallback_extraction(self, content: str) -> str:
        lines = content.splitlines()
        important_lines = [l.strip() for l in lines if l.strip().startswith(("#", "-", "*")) or "important" in l.lower() or "note" in l.lower()]
        if not important_lines:
            important_lines = [l.strip() for l in lines if len(l.strip()) > 20][:10]

        return "## Extracted Key Insights\n" + "\n".join(f"- {line}" for line in important_lines)
