"""
Shadow Self-Improvement System

Continuously identifies opportunities to improve Shadow's capabilities:
  - Missing capabilities
  - Broken or failing tools
  - Inefficient procedures
  - Repeated errors
  - New required agents
  - Better workflows
  - Better documentation

Self-improvement is controlled. Shadow may propose, test, and deploy improvements
inside approved boundaries, but it must NEVER remove or bypass its own Guardian,
authorization system, safety controls, or foundational rules (core principles).
"""
import os
import json
import time
import re
from pathlib import Path
from typing import Dict, Any, List, Optional

from logging.logger import ShadowLogger

log = ShadowLogger.get("shadow.self_improve")

IMPROVEMENT_DIR = Path(__file__).parent / "data"


class SelfImprovement:
    """Analyzes Shadow's performance and proposes controlled improvements."""

    def __init__(self, core=None):
        self.core = core
        self.data_dir = IMPROVEMENT_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.proposals_file = self.data_dir / "proposals.json"
        self.error_log = self.data_dir / "error_patterns.json"
        self.proposals = self._load_proposals()
        self.error_patterns = self._load_error_patterns()

    def _load_proposals(self) -> List[dict]:
        if self.proposals_file.exists():
            try:
                with open(self.proposals_file) as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    def _load_error_patterns(self) -> List[dict]:
        if self.error_log.exists():
            try:
                with open(self.error_log) as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    def _save_proposals(self):
        with open(self.proposals_file, "w") as f:
            json.dump(self.proposals, f, indent=2)

    def _save_error_patterns(self):
        with open(self.error_log, "w") as f:
            json.dump(self.error_patterns, f, indent=2)

    def record_error(self, agent_name: str, task_description: str, error: str):
        """Record an error for pattern analysis."""
        entry = {
            "agent": agent_name,
            "task": task_description[:200],
            "error": error[:500],
            "timestamp": time.time(),
        }
        self.error_patterns.append(entry)
        if len(self.error_patterns) > 500:
            self.error_patterns = self.error_patterns[-500:]
        self._save_error_patterns()
        log.debug(f"Recorded error from {agent_name}: {error[:60]}")

    def analyze_errors(self) -> List[dict]:
        """Find repeated error patterns that indicate systemic issues."""
        if not self.error_patterns:
            return []

        # Group by agent + error signature
        signatures = {}
        for err in self.error_patterns:
            # Create a signature from the first meaningful line of the error
            sig_line = err["error"].split("\n")[0][:80]
            sig = f"{err['agent']}:{sig_line}"
            if sig not in signatures:
                signatures[sig] = {"count": 0, "examples": [], "agent": err["agent"]}
            signatures[sig]["count"] += 1
            if len(signatures[sig]["examples"]) < 3:
                signatures[sig]["examples"].append(err)

        # Report patterns that repeat 3+ times
        patterns = []
        for sig, data in signatures.items():
            if data["count"] >= 3:
                patterns.append({
                    "signature": sig,
                    "count": data["count"],
                    "agent": data["agent"],
                    "examples": data["examples"],
                    "recommendation": self._suggest_fix(data["agent"], sig, data["count"]),
                })

        return sorted(patterns, key=lambda x: x["count"], reverse=True)

    def _suggest_fix(self, agent: str, signature: str, count: int) -> str:
        """Generate a recommendation for a repeated error pattern."""
        if "ImportError" in signature or "ModuleNotFound" in signature:
            return f"Agent {agent} is missing a dependency — consider installing the module or adding a fallback."
        if "PermissionError" in signature:
            return f"Agent {agent} has persistent permission issues — review Guardian permissions for this agent."
        if "Timeout" in signature:
            return f"Agent {agent} is timing out frequently — consider increasing timeout or optimizing the operation."
        if "FileNotFound" in signature or "No such file" in signature:
            return f"Agent {agent} repeatedly can't find files — check path resolution logic."
        return f"Agent {agent} has a recurring error ({count} occurrences) — investigate and patch."

    def identify_missing_capabilities(self) -> List[dict]:
        """Check if there are task types that no agent can handle."""
        if not self.core:
            return []

        missing = []
        test_requests = [
            ("send an email", "email_agent"),
            ("manage a database", "database_agent"),
            ("browse a website", "web_agent"),
            ("translate text to French", "translation_agent"),
            ("convert a video format", "media_agent"),
        ]

        for request, suggested_name in test_requests:
            routed = self.core._select_agent(request)
            if routed == "coding_agent":  # Default fallback = no specialist exists
                missing.append({
                    "request": request,
                    "suggested_agent": suggested_name,
                    "current_routing": routed,
                    "note": f"No specialist for '{request}' — would benefit from a {suggested_name}",
                })

        return missing

    def propose_improvement(self, improvement_type: str, description: str,
                             details: Optional[dict] = None) -> dict:
        """Create a new improvement proposal (does NOT auto-deploy)."""
        # Safety: never propose removing safety mechanisms
        safety_keywords = ["guardian", "guardian.sh", "core_principles", "safety",
                          "authorization", "sandbox", "approve"]
        desc_lower = description.lower()
        if any(kw in desc_lower for kw in safety_keywords):
            return {
                "success": False,
                "error": "BLOCKED: Cannot propose changes to safety mechanisms, Guardian, "
                         "core principles, or authorization system."
            }

        proposal = {
            "id": f"imp_{int(time.time())}",
            "type": improvement_type,
            "description": description,
            "details": details or {},
            "status": "proposed",
            "created": time.time(),
            "approved": False,
        }
        self.proposals.append(proposal)
        self._save_proposals()
        log.info(f"Improvement proposed: {improvement_type} — {description[:80]}")
        return {"success": True, "proposal_id": proposal["id"]}

    def approve_proposal(self, proposal_id: str) -> dict:
        """Approve a proposal (requires human authorization)."""
        for p in self.proposals:
            if p["id"] == proposal_id:
                p["approved"] = True
                p["status"] = "approved"
                self._save_proposals()
                log.info(f"Proposal {proposal_id} approved")
                return {"success": True, "proposal": p}
        return {"success": False, "error": "Proposal not found"}

    def list_proposals(self, status: Optional[str] = None) -> List[dict]:
        """List proposals, optionally filtered by status."""
        if status:
            return [p for p in self.proposals if p["status"] == status]
        return self.proposals

    def run_analysis(self) -> dict:
        """Run a full self-improvement analysis cycle."""
        results = {
            "error_patterns": self.analyze_errors(),
            "missing_capabilities": self.identify_missing_capabilities(),
            "pending_proposals": [p for p in self.proposals if p["status"] == "proposed"],
            "approved_proposals": [p for p in self.proposals if p["status"] == "approved"],
            "total_errors_recorded": len(self.error_patterns),
            "total_proposals": len(self.proposals),
        }

        # Auto-propose fixes for severe error patterns
        for pattern in results["error_patterns"]:
            if pattern["count"] >= 5:
                self.propose_improvement(
                    "error_fix",
                    f"Fix recurring error in {pattern['agent']}: {pattern['signature'][:60]}",
                    {"pattern": pattern, "auto_generated": True}
                )

        # Auto-propose new agents for missing capabilities
        for cap in results["missing_capabilities"]:
            self.propose_improvement(
                "new_agent",
                f"Create {cap['suggested_agent']} for: {cap['request']}",
                {"suggested_agent": cap["suggested_agent"], "auto_generated": True}
            )

        return results
