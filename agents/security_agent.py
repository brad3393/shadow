"""
SecurityAgent — Expert agent for auditing code, permissions, and security vulnerabilities.
"""
import os
import re
import ast
from pathlib import Path
from typing import Dict, Any, List, Optional

from core.base import BaseAgent
from logging.logger import ShadowLogger

log = ShadowLogger.get("shadow.agents.security")


class SecurityAgent(BaseAgent):
    name: str = "security_agent"
    description: str = "Audits permissions, scans code for security vulnerabilities, and checks safety."

    def can_handle(self, task_description: str) -> bool:
        keywords = [
            "security", "audit", "vulnerability", "permission", "check safety",
            "scan", "secrets", "hardcoded", "malware", "safety check"
        ]
        desc_lower = task_description.lower()
        return any(kw in desc_lower for kw in keywords)

    def execute(self, task: dict) -> dict:
        desc = task.get("description", task.get("task", ""))
        target_path = task.get("path") or task.get("file_path") or task.get("target") or "."

        log.info(f"SecurityAgent auditing target: {target_path}")

        path = Path(target_path)
        issues = []

        if path.is_file():
            issues.extend(self._scan_file(path))
        elif path.is_dir():
            for f in path.rglob("*"):
                if f.is_file() and not f.name.startswith(".") and f.suffix in [".py", ".js", ".json", ".sh", ".env", ".yml", ".yaml"]:
                    issues.extend(self._scan_file(f))

        report = self._format_report(target_path, issues)
        return {
            "success": True,
            "output": report,
            "error": None,
            "vulnerabilities_found": len(issues)
        }

    def _scan_file(self, file_path: Path) -> List[dict]:
        issues = []

        # 1. Permission checks
        try:
            stat = file_path.stat()
            mode = stat.st_mode
            if mode & 0o002:  # World writable
                issues.append({
                    "file": str(file_path),
                    "severity": "HIGH",
                    "issue": "World-writable file permissions (chmod o+w)"
                })
        except Exception:
            pass

        # 2. Content security scan
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")

            dangerous_patterns = [
                (r"\beval\s*\(", "HIGH", "Use of eval() function"),
                (r"\bexec\s*\(", "HIGH", "Use of exec() function"),
                (r"os\.system\s*\(", "MEDIUM", "Use of os.system()"),
                (r"subprocess\.\w+\(.*shell\s*=\s*True", "HIGH", "Subprocess execution with shell=True"),
                (r"chmod\s+777", "HIGH", "Insecure file permission modification (chmod 777)"),
                (r"http://", "LOW", "Insecure HTTP URL found"),
            ]

            for pattern, severity, msg in dangerous_patterns:
                for match in re.finditer(pattern, content):
                    line_no = content[:match.start()].count("\n") + 1
                    issues.append({
                        "file": str(file_path),
                        "line": line_no,
                        "severity": severity,
                        "issue": msg
                    })

            # Hardcoded secrets detection
            secret_patterns = [
                (r"(?i)(api[_-]?key|secret|password|passwd|token)\s*=\s*['\"][^'\"]{8,}['\"]", "HIGH", "Potential hardcoded secret or API key"),
                (r"-----BEGIN (RSA|EC|PRIVATE) KEY-----", "CRITICAL", "Private key stored in file")
            ]

            for pattern, severity, msg in secret_patterns:
                for match in re.finditer(pattern, content):
                    line_no = content[:match.start()].count("\n") + 1
                    issues.append({
                        "file": str(file_path),
                        "line": line_no,
                        "severity": severity,
                        "issue": msg
                    })

        except Exception as e:
            log.warning(f"Could not scan file {file_path}: {e}")

        return issues

    def _format_report(self, target: str, issues: List[dict]) -> str:
        lines = [f"=== Security Audit Report for '{target}' ==="]
        lines.append(f"Total issues found: {len(issues)}\n")

        if not issues:
            lines.append("✓ No obvious security issues or vulnerabilities found.")
            return "\n".join(lines)

        for issue in issues:
            line_str = f" (line {issue['line']})" if "line" in issue else ""
            lines.append(f"[{issue['severity']}] {issue['file']}{line_str}: {issue['issue']}")

        return "\n".join(lines)
