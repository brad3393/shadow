"""
HardwareAgent — Expert agent for monitoring system hardware status and health.
"""
import os
import shutil
import platform
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

from core.base import BaseAgent
from logging.logger import ShadowLogger

log = ShadowLogger.get("shadow.agents.hardware")


class HardwareAgent(BaseAgent):
    name: str = "hardware_agent"
    description: str = "Monitors system hardware resources including CPU, RAM, disk usage, battery, and overall system health."

    def can_handle(self, task_description: str) -> bool:
        keywords = [
            "hardware", "battery", "cpu", "ram", "disk", "temperature",
            "monitor", "memory usage", "gpu", "system health", "specs"
        ]
        desc_lower = task_description.lower()
        return any(kw in desc_lower for kw in keywords)

    def _get_hardware_monitor(self):
        try:
            from hardware.hardware_monitor import HardwareMonitor
            return HardwareMonitor()
        except Exception as e:
            log.debug(f"HardwareMonitor module unavailable: {e}")
            return None

    def execute(self, task: dict) -> dict:
        desc = task.get("description", task.get("task", ""))
        log.info(f"HardwareAgent checking status: {desc[:80]}")

        hw_monitor = self._get_hardware_monitor()

        if hw_monitor and hasattr(hw_monitor, "get_status"):
            try:
                status = hw_monitor.get_status()
                return {
                    "success": True,
                    "output": f"Hardware Status Report:\n{status}",
                    "error": None,
                    "hardware_data": status
                }
            except Exception as e:
                log.warning(f"HardwareMonitor error: {e}")

        # Fallback system resource gathering
        report = self._fallback_hardware_check()
        return {
            "success": True,
            "output": report,
            "error": None
        }

    def _fallback_hardware_check(self) -> str:
        lines = ["=== Hardware Status & System Health ==="]
        lines.append(f"OS Platform: {platform.system()} {platform.release()} ({platform.machine()})")

        # CPU load
        try:
            load = os.getloadavg()
            lines.append(f"CPU Load Average (1m, 5m, 15m): {load[0]:.2f}, {load[1]:.2f}, {load[2]:.2f}")
        except Exception:
            lines.append("CPU Load: Unavailable")

        # Disk usage
        try:
            total, used, free = shutil.disk_usage("/")
            lines.append(
                f"Disk Usage (/): {used / (1024**3):.2f} GB used / "
                f"{total / (1024**3):.2f} GB total ({free / total * 100:.1f}% free)"
            )
        except Exception as e:
            lines.append(f"Disk Usage: Error ({e})")

        # RAM Info
        try:
            mem_path = Path("/proc/meminfo")
            if mem_path.exists():
                mem_data = {}
                for line in mem_path.read_text().splitlines()[:5]:
                    parts = line.split(":")
                    if len(parts) == 2:
                        mem_data[parts[0].strip()] = parts[1].strip()
                lines.append(f"RAM Info: Total={mem_data.get('MemTotal', 'N/A')}, Free={mem_data.get('MemFree', 'N/A')}, Available={mem_data.get('MemAvailable', 'N/A')}")
            else:
                lines.append("RAM Info: /proc/meminfo not available")
        except Exception:
            lines.append("RAM Info: Unavailable")

        return "\n".join(lines)
