"""
ResearchAgent — Expert agent for gathering information, reading files, and searching knowledge.
"""
import os
import re
from pathlib import Path
from typing import Dict, Any, List, Optional

from core.base import BaseAgent
from logging.logger import ShadowLogger
from config.config import DATA_DIR, KNOWLEDGE_DIR

log = ShadowLogger.get("shadow.agents.research")


class ResearchAgent(BaseAgent):
    name: str = "research_agent"
    description: str = "Gathers information, reads files, searches knowledge bases, and summarizes findings."

    def can_handle(self, task_description: str) -> bool:
        keywords = [
            "research", "find", "search", "analyze", "summarize", "read",
            "lookup", "gather", "investigate", "scan files", "explore"
        ]
        desc_lower = task_description.lower()
        return any(kw in desc_lower for kw in keywords)

    def execute(self, task: dict) -> dict:
        desc = task.get("description", task.get("task", ""))
        target_path = task.get("path") or task.get("file_path") or task.get("target")
        query = task.get("query")

        log.info(f"ResearchAgent executing: {desc[:80]}")

        findings = []

        # Extract search query or target from description if not explicit
        if not query and not target_path:
            path_match = re.search(r"(\b[\w\-_/.]+\.(?:txt|md|py|json|log|csv)\b)", desc)
            if path_match:
                target_path = path_match.group(1)
            else:
                query = desc

        if target_path:
            path = Path(target_path)
            if path.exists():
                if path.is_file():
                    try:
                        content = path.read_text(encoding="utf-8", errors="ignore")
                        findings.append(f"--- Content of {path} (first 2000 chars) ---\n" + content[:2000])
                    except Exception as e:
                        findings.append(f"Error reading file {path}: {e}")
                elif path.is_dir():
                    try:
                        files = list(path.rglob("*"))[:50]
                        file_list = "\n".join([f"- {f.relative_to(path)}" for f in files if f.is_file()])
                        findings.append(f"--- Directory contents of {path} ({len(files)} items) ---\n" + file_list)
                    except Exception as e:
                        findings.append(f"Error scanning directory {path}: {e}")
            else:
                findings.append(f"Target path '{target_path}' does not exist.")

        # Search local knowledge & data dir
        if query:
            search_results = self._search_directory(query, KNOWLEDGE_DIR)
            if not search_results:
                search_results = self._search_directory(query, DATA_DIR)
            if search_results:
                findings.append(f"--- Search results for query '{query}' ---\n" + "\n".join(search_results))

        if not findings:
            findings.append(f"No specific files or matches found for task: {desc}")

        summary = "\n\n".join(findings)
        return {
            "success": True,
            "output": summary,
            "error": None
        }

    def _search_directory(self, query: str, directory: Path, max_matches: int = 10) -> List[str]:
        results = []
        if not directory.exists():
            return results

        pattern = re.compile(re.escape(query), re.IGNORECASE)
        count = 0

        for file_path in directory.rglob("*"):
            if count >= max_matches:
                break
            if file_path.is_file() and file_path.suffix in [".txt", ".md", ".json", ".log", ".py"]:
                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                    matches = pattern.findall(content)
                    if matches:
                        results.append(f"File: {file_path.name} ({len(matches)} matches found)")
                        count += 1
                except Exception:
                    continue
        return results
