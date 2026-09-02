"""
FileAgent — Expert agent for managing file operations with Guardian pre-checks.
"""
import os
import shutil
import re
from pathlib import Path
from typing import Dict, Any, Optional

from core.base import BaseAgent
from logging.logger import ShadowLogger

log = ShadowLogger.get("shadow.agents.file")


class FileAgent(BaseAgent):
    name: str = "file_agent"
    description: str = "Manages file and directory operations (create, move, copy, delete, organize) safely."

    def can_handle(self, task_description: str) -> bool:
        keywords = [
            "manage file", "move file", "copy file", "delete file",
            "rename file", "create folder", "mkdir", "archive file",
            "file operation", "clean up files", "file permission",
            "list files", "list all files", "list directory",
            "show files", "show all files", "organize files",
            "sort files", "directory contents",
            "list contents"
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
        action = task.get("action", "").lower()
        src = task.get("src") or task.get("source") or task.get("path") or task.get("file_path")
        dst = task.get("dst") or task.get("destination") or task.get("target")

        log.info(f"FileAgent executing: {desc[:80]}")

        guardian = self._get_guardian()

        desc_lower = desc.lower()
        if not action:
            if "delete" in desc_lower or "remove" in desc_lower or "clean" in desc_lower:
                action = "delete"
            elif "move" in desc_lower or "rename" in desc_lower:
                action = "move"
            elif "copy" in desc_lower:
                action = "copy"
            elif "create" in desc_lower or "mkdir" in desc_lower or "touch" in desc_lower:
                action = "create"
            elif "organize" in desc_lower:
                action = "organize"
            else:
                action = "info"

        if not src:
            paths = re.findall(r"(\b[\w\-_/.]+\.[\w]+\b|\b[\w\-_/.]+/)", desc)
            if paths:
                src = paths[0]
                if len(paths) > 1:
                    dst = paths[1]

        # Guardian pre-check
        if guardian:
            allowed, reason = guardian.pre_check("file_operation", {"action": action, "src": src, "dst": dst})
            if not allowed:
                return {
                    "success": False,
                    "output": f"Guardian blocked file operation '{action}': {reason}",
                    "error": f"Guardian blocked: {reason}"
                }

        try:
            if action == "delete":
                if not src or not os.path.exists(src):
                    return {"success": False, "output": f"Path '{src}' does not exist.", "error": "Path not found"}
                p = Path(src)
                if p.is_file():
                    p.unlink()
                elif p.is_dir():
                    shutil.rmtree(p)
                return {"success": True, "output": f"Successfully deleted {src}", "error": None}

            elif action == "move":
                if not src or not dst:
                    return {"success": False, "output": "Move requires source and destination paths.", "error": "Missing paths"}
                shutil.move(src, dst)
                return {"success": True, "output": f"Successfully moved {src} to {dst}", "error": None}

            elif action == "copy":
                if not src or not dst:
                    return {"success": False, "output": "Copy requires source and destination paths.", "error": "Missing paths"}
                if os.path.isdir(src):
                    shutil.copytree(src, dst, dirs_exist_ok=True)
                else:
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(src, dst)
                return {"success": True, "output": f"Successfully copied {src} to {dst}", "error": None}

            elif action == "create":
                if not src:
                    return {"success": False, "output": "Create requires target path.", "error": "Missing path"}
                p = Path(src)
                if desc_lower.find("dir") != -1 or desc_lower.find("folder") != -1 or src.endswith("/"):
                    p.mkdir(parents=True, exist_ok=True)
                    return {"success": True, "output": f"Created directory {src}", "error": None}
                else:
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.touch(exist_ok=True)
                    return {"success": True, "output": f"Created file {src}", "error": None}

            elif action == "organize":
                target_dir = Path(src if src else ".")
                if not target_dir.exists() or not target_dir.is_dir():
                    return {"success": False, "output": f"Directory '{target_dir}' not found.", "error": "Directory not found"}

                organized = 0
                for f in list(target_dir.iterdir()):
                    if f.is_file() and not f.name.startswith("."):
                        ext = f.suffix.lstrip(".").lower() or "misc"
                        category_dir = target_dir / ext
                        category_dir.mkdir(exist_ok=True)
                        shutil.move(str(f), str(category_dir / f.name))
                        organized += 1
                return {"success": True, "output": f"Organized {organized} files in {target_dir}", "error": None}

            else:
                return {
                    "success": True,
                    "output": f"File agent processed task: {desc} (src={src}, dst={dst})",
                    "error": None
                }

        except Exception as e:
            log.error(f"File operation failed: {e}")
            return {"success": False, "output": f"File operation failed: {e}", "error": str(e)}
