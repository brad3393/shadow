"""
PlanningAgent — Expert agent for creating execution strategies and breaking down complex goals.
"""
import json
from pathlib import Path
from typing import Dict, Any, List, Optional

from core.base import BaseAgent
from logging.logger import ShadowLogger

log = ShadowLogger.get("shadow.agents.planning")


class PlanningAgent(BaseAgent):
    name: str = "planning_agent"
    description: str = "Breaks down complex goals, creates strategic plans, and designs roadmaps."

    def can_handle(self, task_description: str) -> bool:
        keywords = [
            "plan", "strategy", "roadmap", "break down", "organize",
            "architecture", "steps", "workflow", "milestones", "schedule"
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
        goal = task.get("goal") or desc

        log.info(f"PlanningAgent breaking down goal: {goal[:80]}")

        ollama = self._get_ollama()

        if ollama:
            prompt = (
                f"You are a strategic AI planning agent. Create a step-by-step execution plan for the following goal:\n"
                f"Goal: {goal}\n\n"
                f"Provide a clear, structured Markdown plan with numbered steps, subtasks, risks, and verification steps."
            )
            try:
                plan = ollama.generate(prompt)
                return {
                    "success": True,
                    "output": plan,
                    "error": None
                }
            except Exception as e:
                log.warning(f"Ollama planning generation failed: {e}")
                plan = self._fallback_plan(goal)
        else:
            plan = self._fallback_plan(goal)

        return {
            "success": True,
            "output": plan,
            "error": None
        }

    def _fallback_plan(self, goal: str) -> str:
        return (
            f"# Execution Plan for: {goal}\n\n"
            f"## Phase 1: Requirements & Discovery\n"
            f"- Step 1.1: Analyze target requirements and dependencies.\n"
            f"- Step 1.2: Audit existing files and directory structure.\n\n"
            f"## Phase 2: Core Implementation\n"
            f"- Step 2.1: Develop initial prototypes and core logic.\n"
            f"- Step 2.2: Refactor and integrate with existing Shadow modules.\n\n"
            f"## Phase 3: Verification & Safety\n"
            f"- Step 3.1: Run unit tests and security checks.\n"
            f"- Step 3.2: Verify hardware status and error handling.\n\n"
            f"## Phase 4: Finalization\n"
            f"- Step 4.1: Document implementation and generate user guides."
        )
