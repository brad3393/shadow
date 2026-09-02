"""
Guardian Security Layer — Shadow Network.

Implements GuardianCheck interface to enforce execution permissions, sandbox boundaries,
dangerous pattern detection, file access restrictions, user approval requirements,
backups, rollbacks, and audit logging.
"""
import os
import re
import sys
import json
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Set

from config.config import (
    CHECKPOINTS,
    DATA_DIR,
    LOGS_DIR,
    REQUIRE_APPROVAL_FOR,
    SHADOW_ROOT,
)
from logging.logger import ShadowLogger
from core.base import GuardianCheck


class Guardian(GuardianCheck):
    """
    Guardian security system enforcing execution safety, isolation,
    checkpoints, rollbacks, and audit logs.
    """

    DANGEROUS_PATTERNS = [
        r"rm\s+(-[a-zA-Z]*r[a-zA-Z]*f|-[a-zA-Z]*f[a-zA-Z]*r)\s+[/~*.]+",
        r"rm\s+-rf\s+/",
        r"\bsudo\b",
        r"\bchmod\s+(-R\s+)?777\b",
        r"\bdd\s+if=",
        r"\bmkfs(\.[a-z0-9]+)?\b",
        r"\bfdisk\b",
        r"\bshutdown\b",
        r"\breboot\b",
        r":\(\)\{\s*:\|:&\s*\};:",
        r"wget\s+.*\|\s*(sh|bash|zsh|python)",
        r"curl\s+.*\|\s*(sh|bash|zsh|python)",
        r"base64\s+-d.*\|\s*(sh|bash)",
    ]

    EXPLICIT_DANGEROUS_STRINGS = [
        "rm -rf /",
        "sudo ",
        "chmod 777",
        "dd if=",
        "mkfs",
        "fdisk",
        "shutdown",
        "reboot",
        ":(){:|:&};:",
        "wget ... | sh",
        "curl ... | bash",
    ]

    RESTRICTED_SYSTEM_DIRS = [
        "/etc",
        "/proc",
        "/sys",
        "/dev",
        "/boot",
        "/root",
        "/var",
        "/usr",
        "/bin",
        "/sbin",
    ]

    SENSITIVE_FILES = [
        "/etc/shadow",
        "/etc/passwd",
        ".env",
        "id_rsa",
        "id_ed25519",
    ]

    def __init__(self, mode: str = "autonomous", interactive: bool = False):
        self.mode = mode.lower()
        self.interactive = interactive or (self.mode == "interactive")
        self.logger = ShadowLogger.get("shadow.guardian")
        self.audit_log_path = LOGS_DIR / "audit.log"
        self._ensure_dirs()

    def _ensure_dirs(self):
        """Ensure critical directories exist."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        CHECKPOINTS.mkdir(parents=True, exist_ok=True)

    # ─── Pattern & Permission Checks ───────────────────────────────

    def _detect_dangerous_patterns(self, text: str) -> Tuple[bool, str]:
        """
        Scan text for dangerous commands, shell injections, or fork bombs.
        Returns (is_dangerous, reason).
        """
        if not text:
            return False, ""

        # Check explicit strings
        for dstr in ["rm -rf /", "chmod 777", "dd if=", ":(){:|:&};:"]:
            if dstr in text:
                return True, f"Explicit dangerous pattern detected: '{dstr}'"

        if "sudo " in text or text.strip().startswith("sudo"):
            return True, "Explicit dangerous pattern detected: 'sudo '"

        # Check regex patterns
        for pattern in self.DANGEROUS_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return True, f"Dangerous command pattern matched: '{match.group(0)}'"

        # Check wget/curl pipe to sh/bash
        if re.search(r"(wget|curl)\s+.*\|\s*(sh|bash)", text, re.IGNORECASE):
            return True, "Dangerous operation detected: piping web download to shell execution"

        return False, ""

    def _check_file_access(self, action: str, context: dict) -> Tuple[bool, str]:
        """
        Check if file access violates sandbox boundaries or access restrictions.
        Returns (allowed, reason).
        """
        paths_to_check = []
        for key in ["path", "file_path", "target", "dir", "destination"]:
            val = context.get(key)
            if val:
                paths_to_check.append(str(val))

        for p_str in paths_to_check:
            # Check for sensitive system file targets
            for sys_dir in self.RESTRICTED_SYSTEM_DIRS:
                if p_str == sys_dir or p_str.startswith(f"{sys_dir}/"):
                    return False, f"File access restricted: system directory '{sys_dir}' access prohibited"

            for sens in self.SENSITIVE_FILES:
                if sens in p_str:
                    return False, f"File access restricted: sensitive target '{sens}'"

            # Check sandbox boundary escaping
            try:
                resolved = Path(p_str).resolve()
                # If path is absolute and outside SHADOW_ROOT and DATA_DIR for write/delete operations
                if action in ["write_file", "delete_file", "modify_system_config", "irreversible_ops"]:
                    if not (str(resolved).startswith(str(SHADOW_ROOT)) or str(resolved).startswith(str(DATA_DIR))):
                        return False, f"Sandbox boundary violation: target '{resolved}' is outside allowed directories"
            except Exception:
                pass

        return True, ""

    def _check_process_restrictions(self, action: str, context: dict) -> Tuple[bool, str]:
        """
        Check process spawn restrictions.
        Returns (allowed, reason).
        """
        cmd = context.get("command", "")
        if isinstance(cmd, str):
            if "fork" in cmd and ":()" in cmd:
                return False, "Process restriction: fork bomb detected"
        return True, ""

    # ─── GuardianCheck Interface Implementation ───────────────────

    def pre_check(self, action: str, context: dict) -> Tuple[bool, str]:
        """
        Hook before action execution.
        Returns (allowed, reason).
        """
        if context is None:
            context = {}

        cmd = str(context.get("command", ""))
        task = str(context.get("task", ""))
        details = f"action={action} command={cmd} task={task}"
        text_to_scan = f"{action} {cmd} {task} {json.dumps(context, default=str)}"

        # 1. Dangerous pattern detection
        is_dangerous, reason = self._detect_dangerous_patterns(text_to_scan)
        if is_dangerous:
            self.audit_log(action, False, reason)
            self.logger.warning(f"Guardian PRE-CHECK BLOCKED: {reason}")
            return False, reason

        # 2. File access & Sandbox restrictions
        file_ok, file_reason = self._check_file_access(action, context)
        if not file_ok:
            self.audit_log(action, False, file_reason)
            self.logger.warning(f"Guardian PRE-CHECK BLOCKED: {file_reason}")
            return False, file_reason

        # 3. Process restrictions
        proc_ok, proc_reason = self._check_process_restrictions(action, context)
        if not proc_ok:
            self.audit_log(action, False, proc_reason)
            self.logger.warning(f"Guardian PRE-CHECK BLOCKED: {proc_reason}")
            return False, proc_reason

        # 4. User approval requirements
        category = context.get("category", "")
        if self.requires_approval(action) or self.requires_approval(category):
            approved = self.request_user_approval(action, details)
            if not approved:
                reason = f"Action '{action}' requires user approval but was not approved."
                self.audit_log(action, False, reason)
                self.logger.warning(f"Guardian PRE-CHECK BLOCKED: {reason}")
                return False, reason

        reason = "Action allowed by Guardian pre-check."
        self.audit_log(action, True, reason)
        self.logger.info(f"Guardian PRE-CHECK PASSED: {action}")
        return True, reason

    def post_check(self, action: str, result: dict) -> Tuple[bool, str]:
        """
        Hook after action execution.
        Returns (safe, reason).
        """
        if result is None:
            result = {}

        output = str(result.get("output", ""))
        error = str(result.get("error", ""))
        combined = f"{output}\n{error}"

        # 1. Dangerous output detection
        is_dangerous, reason = self._detect_dangerous_patterns(combined)
        if is_dangerous:
            post_reason = f"Post-check detected dangerous pattern in output: {reason}"
            self.audit_log(action, False, post_reason)
            self.logger.warning(f"Guardian POST-CHECK FAILED: {post_reason}")
            return False, post_reason

        # Sensitive leak detection
        sensitive_markers = ["BEGIN PRIVATE KEY", "BEGIN RSA PRIVATE KEY", "root:$1$", "root:$6$"]
        for marker in sensitive_markers:
            if marker in combined:
                post_reason = f"Post-check detected sensitive data exposure ('{marker}') in result output."
                self.audit_log(action, False, post_reason)
                self.logger.warning(f"Guardian POST-CHECK FAILED: {post_reason}")
                return False, post_reason

        # 2. System file modification verification
        modified_files = result.get("modified_files", []) or result.get("files_changed", [])
        if isinstance(modified_files, list):
            for file_item in modified_files:
                file_str = str(file_item)
                for sys_dir in self.RESTRICTED_SYSTEM_DIRS:
                    if file_str.startswith(sys_dir):
                        post_reason = f"Post-check failed: system file '{file_str}' was modified."
                        self.audit_log(action, False, post_reason)
                        self.logger.warning(f"Guardian POST-CHECK FAILED: {post_reason}")
                        return False, post_reason

        reason = "Result verified safe by Guardian post-check."
        self.audit_log(action, True, reason)
        self.logger.info(f"Guardian POST-CHECK PASSED: {action}")
        return True, reason

    # ─── Approval Handling ─────────────────────────────────────────

    def requires_approval(self, action: str) -> bool:
        """Check if action is in REQUIRE_APPROVAL_FOR set or matches an approval required item."""
        if not action:
            return False
        if action in REQUIRE_APPROVAL_FOR:
            return True
        action_lower = action.lower()
        for item in REQUIRE_APPROVAL_FOR:
            if item.lower() in action_lower:
                return True
        return False

    def request_user_approval(self, action: str, details: str = "") -> bool:
        """
        Request approval from user.
        In interactive mode: prompts user.
        In autonomous mode: returns False.
        """
        if not self.interactive or self.mode == "autonomous":
            self.logger.warning(
                f"Action '{action}' requires user approval, but Guardian is in autonomous mode. Denying."
            )
            return False

        try:
            prompt_msg = f"\n[GUARDIAN APPROVAL REQUIRED] Action: {action}\nDetails: {details}\nApprove? [y/N]: "
            user_input = input(prompt_msg).strip().lower()
            approved = user_input in ["y", "yes"]
            self.logger.info(f"User approval prompt for '{action}' returned: {approved}")
            return approved
        except (EOFError, KeyboardInterrupt):
            self.logger.warning(f"User approval prompt for '{action}' interrupted or closed. Denying.")
            return False

    # ─── Checkpoint & Rollback System ──────────────────────────────

    def create_checkpoint(self, name: str, source_dirs: Optional[List[str]] = None) -> str:
        """
        Create a snapshot checkpoint of system directories or specified paths.
        Copies files to CHECKPOINTS dir.
        Returns checkpoint_id.
        """
        safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", name)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        checkpoint_id = f"{safe_name}_{timestamp}"
        cp_dir = CHECKPOINTS / checkpoint_id
        data_dir = cp_dir / "data"
        cp_dir.mkdir(parents=True, exist_ok=True)
        data_dir.mkdir(parents=True, exist_ok=True)

        if source_dirs is None:
            source_dirs = [
                str(DATA_DIR / "memory"),
                str(DATA_DIR / "tasks"),
                str(DATA_DIR / "vault"),
                str(SHADOW_ROOT / "shadow" / "config"),
            ]

        saved_files = []
        manifest_sources = []

        for src_str in source_dirs:
            src_path = Path(src_str).resolve()
            if not src_path.exists():
                continue

            manifest_sources.append(str(src_path))
            try:
                rel_path = src_path.relative_to(SHADOW_ROOT)
            except ValueError:
                rel_path = Path(src_path.name)

            dest_target = data_dir / rel_path

            if src_path.is_file():
                dest_target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_path, dest_target)
                saved_files.append(str(rel_path))
            elif src_path.is_dir():
                dest_target.mkdir(parents=True, exist_ok=True)
                for root, _, files in os.walk(src_path):
                    for f in files:
                        full_file = Path(root) / f
                        file_rel = full_file.relative_to(src_path)
                        dest_file = dest_target / file_rel
                        dest_file.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(full_file, dest_file)
                        saved_files.append(str(rel_path / file_rel))

        metadata = {
            "id": checkpoint_id,
            "name": name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "file_count": len(saved_files),
            "source_dirs": manifest_sources,
            "saved_files": saved_files,
        }

        with open(cp_dir / "checkpoint.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        self.audit_log("create_checkpoint", True, f"Created checkpoint '{checkpoint_id}' with {len(saved_files)} files.")
        self.logger.info(f"Checkpoint '{checkpoint_id}' created successfully ({len(saved_files)} files).")
        return checkpoint_id

    def rollback(self, checkpoint_id: str) -> bool:
        """
        Restore state from checkpoint_id or checkpoint name.
        Returns True on success, False on failure.
        """
        target_cp = CHECKPOINTS / checkpoint_id
        if not target_cp.exists():
            matches = [
                d for d in CHECKPOINTS.iterdir()
                if d.is_dir() and (d.name == checkpoint_id or d.name.startswith(f"{checkpoint_id}_"))
            ]
            if matches:
                target_cp = sorted(matches, key=lambda p: p.name)[-1]
            else:
                reason = f"Rollback failed: checkpoint '{checkpoint_id}' not found in {CHECKPOINTS}."
                self.audit_log("rollback", False, reason)
                self.logger.error(reason)
                return False

        meta_file = target_cp / "checkpoint.json"
        if not meta_file.exists():
            reason = f"Rollback failed: checkpoint.json metadata missing in '{target_cp}'."
            self.audit_log("rollback", False, reason)
            self.logger.error(reason)
            return False

        try:
            data_dir = target_cp / "data"
            restored_count = 0

            for root, _, files in os.walk(data_dir):
                for f in files:
                    cp_file = Path(root) / f
                    rel_to_data = cp_file.relative_to(data_dir)
                    orig_target = SHADOW_ROOT / rel_to_data
                    orig_target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(cp_file, orig_target)
                    restored_count += 1

            reason = f"Rollback to '{target_cp.name}' completed successfully ({restored_count} files restored)."
            self.audit_log("rollback", True, reason)
            self.logger.info(reason)
            return True
        except Exception as e:
            reason = f"Rollback error for '{checkpoint_id}': {e}"
            self.audit_log("rollback", False, reason)
            self.logger.error(reason)
            return False

    # ─── Audit Logging ─────────────────────────────────────────────

    def audit_log(self, action: str, allowed: bool, reason: str):
        """Write structured entry to LOGS_DIR / audit.log."""
        try:
            timestamp = datetime.now(timezone.utc).isoformat()
            status_str = "ALLOWED" if allowed else "BLOCKED"
            log_line = f"{timestamp} | STATUS={status_str} | ACTION={action} | REASON={reason}\n"

            self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.audit_log_path, "a", encoding="utf-8") as f:
                f.write(log_line)
        except Exception as e:
            self.logger.error(f"Failed to write audit log: {e}")


def self_test() -> bool:
    """Component self-test function for test runners."""
    try:
        g = Guardian(mode="autonomous")

        # Test pre_check with dangerous operations
        allowed, reason = g.pre_check("shell_exec", {"command": "rm -rf /"})
        assert not allowed, "Failed to block rm -rf /"

        allowed, reason = g.pre_check("shell_exec", {"command": "sudo apt update"})
        assert not allowed, "Failed to block sudo"

        allowed, reason = g.pre_check("shell_exec", {"command": "chmod 777 /etc"})
        assert not allowed, "Failed to block chmod 777"

        # Test safe pre_check
        allowed, reason = g.pre_check("read_file", {"path": "shadow/config/config.py"})
        assert allowed, f"Failed safe read_file check: {reason}"

        # Test requires_approval
        assert g.requires_approval("delete_important_files")
        assert g.requires_approval("install_software")

        # Test checkpoint and rollback
        cp_id = g.create_checkpoint("test_self_check")
        assert cp_id is not None
        ok = g.rollback(cp_id)
        assert ok, "Rollback failed"

        # Check audit log written
        assert g.audit_log_path.exists()

        return True
    except Exception as e:
        print(f"Guardian self_test error: {e}")
        return False
