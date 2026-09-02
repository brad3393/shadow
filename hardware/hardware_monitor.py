"""
Shadow Hardware Monitor
Monitors system hardware metrics (CPU, RAM, Storage, Battery, Temp, Network).
Uses Python stdlib only.
"""
import os
import shutil
import subprocess
import platform
import socket
import time
import re
import sys
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

# Ensure parent directory is in sys.path
shadow_dir = str(Path(__file__).resolve().parent.parent)
if shadow_dir not in sys.path:
    sys.path.insert(0, shadow_dir)

from config.config import BATTERY_CRITICAL, STORAGE_CRITICAL, CPU_THROTTLE, DATA_DIR
from logging.logger import ShadowLogger

log = ShadowLogger.get("shadow.hardware")


class HardwareMonitor:
    """Monitors system resources and determines throttle state."""

    def __init__(self):
        self.battery_critical_threshold = BATTERY_CRITICAL
        self.storage_critical_threshold = STORAGE_CRITICAL
        self.cpu_throttle_threshold = CPU_THROTTLE
        self._last_cpu_stat: Optional[Tuple[float, float]] = None

    def get_battery_info(self) -> Tuple[Optional[float], Optional[bool]]:
        """
        Reads battery percentage and charging state.
        Linux: reads /sys/class/power_supply/
        macOS: runs pmset -g batt
        Fallback: (None, None)
        """
        # Linux
        power_supply_dir = Path("/sys/class/power_supply")
        if power_supply_dir.exists():
            try:
                for supply in power_supply_dir.iterdir():
                    type_file = supply / "type"
                    is_battery = False
                    if type_file.exists():
                        try:
                            is_battery = type_file.read_text().strip().lower() == "battery"
                        except Exception:
                            pass
                    if is_battery or supply.name.lower().startswith("bat"):
                        capacity_file = supply / "capacity"
                        status_file = supply / "status"
                        battery_pct = None
                        charging = None
                        if capacity_file.exists():
                            try:
                                battery_pct = float(capacity_file.read_text().strip())
                            except Exception:
                                pass
                        if status_file.exists():
                            try:
                                st = status_file.read_text().strip().lower()
                                charging = st in ["charging", "full"]
                            except Exception:
                                pass
                        if battery_pct is not None:
                            return (battery_pct, charging)
            except Exception as e:
                log.debug(f"Error reading Linux power supply: {e}")

        # macOS
        if platform.system() == "Darwin":
            try:
                res = subprocess.run(
                    ["pmset", "-g", "batt"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if res.returncode == 0:
                    output = res.stdout.lower()
                    pct_match = re.search(r"(\d+)%", output)
                    if pct_match:
                        battery_pct = float(pct_match.group(1))
                        charging = (
                            "charging" in output
                            or "charged" in output
                            or "ac power" in output
                        ) and "discharging" not in output
                        return (battery_pct, charging)
            except Exception as e:
                log.debug(f"Error reading macOS pmset: {e}")

        return (None, None)

    def get_cpu_info(self) -> float:
        """
        Calculates CPU utilization percentage.
        Linux: uses /proc/stat delta or os.getloadavg()
        macOS/other: uses os.getloadavg()
        """
        try:
            if os.path.exists("/proc/stat"):
                with open("/proc/stat", "r", encoding="utf-8") as f:
                    first_line = f.readline()
                if first_line.startswith("cpu "):
                    parts = [float(x) for x in first_line.split()[1:]]
                    idle_time = parts[3] + (parts[4] if len(parts) > 4 else 0.0)
                    total_time = sum(parts)
                    if self._last_cpu_stat is not None:
                        last_idle, last_total = self._last_cpu_stat
                        idle_delta = idle_time - last_idle
                        total_delta = total_time - last_total
                        if total_delta > 0:
                            cpu_pct = (1.0 - idle_delta / total_delta) * 100.0
                            self._last_cpu_stat = (idle_time, total_time)
                            return min(100.0, max(0.0, round(cpu_pct, 2)))
                    self._last_cpu_stat = (idle_time, total_time)
        except Exception as e:
            log.debug(f"Error reading /proc/stat: {e}")

        try:
            if hasattr(os, "getloadavg"):
                load1, _, _ = os.getloadavg()
                ncpu = os.cpu_count() or 1
                return min(100.0, max(0.0, round((load1 / ncpu) * 100.0, 2)))
        except Exception as e:
            log.debug(f"Error reading loadavg: {e}")

        return 0.0

    def get_ram_info(self) -> Tuple[float, float, float]:
        """
        Returns (ram_pct, ram_total_gb, ram_used_gb).
        Linux: uses /proc/meminfo
        macOS/Fallback: uses os.sysconf
        """
        # Linux /proc/meminfo
        if os.path.exists("/proc/meminfo"):
            try:
                mem_total_kb = 0.0
                mem_avail_kb = 0.0
                mem_free_kb = 0.0
                buffers_kb = 0.0
                cached_kb = 0.0

                with open("/proc/meminfo", "r", encoding="utf-8") as f:
                    for line in f:
                        parts = line.split(":")
                        if len(parts) == 2:
                            key = parts[0].strip()
                            val_str = parts[1].strip().split()[0]
                            if key == "MemTotal":
                                mem_total_kb = float(val_str)
                            elif key == "MemAvailable":
                                mem_avail_kb = float(val_str)
                            elif key == "MemFree":
                                mem_free_kb = float(val_str)
                            elif key == "Buffers":
                                buffers_kb = float(val_str)
                            elif key == "Cached":
                                cached_kb = float(val_str)

                if mem_total_kb > 0:
                    if mem_avail_kb > 0:
                        used_kb = mem_total_kb - mem_avail_kb
                    else:
                        used_kb = mem_total_kb - (mem_free_kb + buffers_kb + cached_kb)

                    ram_total_gb = round(mem_total_kb / (1024 * 1024), 2)
                    ram_used_gb = round(used_kb / (1024 * 1024), 2)
                    ram_pct = round((used_kb / mem_total_kb) * 100.0, 2)
                    return (ram_pct, ram_total_gb, ram_used_gb)
            except Exception as e:
                log.debug(f"Error reading /proc/meminfo: {e}")

        # Fallback via os.sysconf
        try:
            pagesize = os.sysconf("SC_PAGE_SIZE")
            total_pages = os.sysconf("SC_PHYS_PAGES")
            avail_pages = os.sysconf("SC_AVPHYS_PAGES")
            total_bytes = pagesize * total_pages
            avail_bytes = pagesize * avail_pages
            used_bytes = total_bytes - avail_bytes

            ram_total_gb = round(total_bytes / (1024**3), 2)
            ram_used_gb = round(used_bytes / (1024**3), 2)
            ram_pct = round((used_bytes / total_bytes) * 100.0, 2) if total_bytes > 0 else 0.0
            return (ram_pct, ram_total_gb, ram_used_gb)
        except Exception as e:
            log.debug(f"Error reading sysconf RAM: {e}")

        return (0.0, 0.0, 0.0)

    def get_storage_info(self) -> Tuple[float, float, float]:
        """
        Returns (storage_total_gb, storage_free_gb, storage_free_pct).
        Uses shutil.disk_usage.
        """
        try:
            target_path = DATA_DIR if DATA_DIR.exists() else "/"
            total, used, free = shutil.disk_usage(target_path)
            storage_total_gb = round(total / (1024**3), 2)
            storage_free_gb = round(free / (1024**3), 2)
            storage_free_pct = (
                round((free / total) * 100.0, 2) if total > 0 else 0.0
            )
            return (storage_total_gb, storage_free_gb, storage_free_pct)
        except Exception as e:
            log.debug(f"Error reading disk usage: {e}")
            return (0.0, 0.0, 0.0)

    def get_network_info(self) -> bool:
        """Checks internet connectivity via socket connection."""
        hosts = [("8.8.8.8", 53), ("1.1.1.1", 53)]
        for host, port in hosts:
            try:
                sock = socket.create_connection((host, port), timeout=1)
                sock.close()
                return True
            except (OSError, socket.error):
                continue
        return False

    def get_temperature(self) -> Optional[float]:
        """Reads system temperature in Celsius on Linux thermal zones."""
        thermal_dir = Path("/sys/class/thermal")
        if thermal_dir.exists():
            temps = []
            try:
                for zone in thermal_dir.glob("thermal_zone*"):
                    temp_file = zone / "temp"
                    if temp_file.exists():
                        try:
                            raw = float(temp_file.read_text().strip())
                            val = raw / 1000.0 if raw > 1000 else raw
                            if 0 <= val <= 150:
                                temps.append(val)
                        except Exception:
                            pass
                if temps:
                    return round(max(temps), 2)
            except Exception as e:
                log.debug(f"Error reading thermal zones: {e}")

        return None

    def get_status(self) -> Dict[str, Any]:
        """
        Returns comprehensive hardware status dictionary.
        Keys:
          battery_pct, charging, cpu_pct, ram_pct, ram_total_gb, ram_used_gb,
          storage_total_gb, storage_free_gb, storage_free_pct, temperature,
          network_connected, battery_critical, storage_critical
        """
        battery_pct, charging = self.get_battery_info()
        cpu_pct = self.get_cpu_info()
        ram_pct, ram_total_gb, ram_used_gb = self.get_ram_info()
        storage_total_gb, storage_free_gb, storage_free_pct = self.get_storage_info()
        temperature = self.get_temperature()
        network_connected = self.get_network_info()

        battery_critical = bool(
            battery_pct is not None
            and battery_pct <= self.battery_critical_threshold
            and not bool(charging)
        )
        storage_critical = bool(storage_free_pct <= self.storage_critical_threshold)

        return {
            "battery_pct": battery_pct,
            "charging": charging,
            "cpu_pct": cpu_pct,
            "ram_pct": ram_pct,
            "ram_total_gb": ram_total_gb,
            "ram_used_gb": ram_used_gb,
            "storage_total_gb": storage_total_gb,
            "storage_free_gb": storage_free_gb,
            "storage_free_pct": storage_free_pct,
            "temperature": temperature,
            "network_connected": network_connected,
            "battery_critical": battery_critical,
            "storage_critical": storage_critical,
        }

    def should_throttle(self) -> bool:
        """Returns True if battery or storage is critical or CPU exceeds threshold."""
        status = self.get_status()
        return bool(
            status["battery_critical"]
            or status["storage_critical"]
            or status["cpu_pct"] >= self.cpu_throttle_threshold
        )

    def monitor_loop(self, interval: int = 60, callback=None, stop_event=None):
        """Simple periodic monitoring loop for background thread execution."""
        log.info(f"Hardware monitor loop started (interval: {interval}s)")
        while True:
            if stop_event and stop_event.is_set():
                break
            try:
                status = self.get_status()
                if callback:
                    callback(status)
            except Exception as e:
                log.error(f"Error in monitor loop: {e}")

            if stop_event:
                if stop_event.wait(timeout=interval):
                    break
            else:
                time.sleep(interval)


def self_test() -> bool:
    """Self-test for HardwareMonitor component validation."""
    log.info("Running HardwareMonitor self_test...")
    try:
        hw = HardwareMonitor()
        status = hw.get_status()

        required_keys = [
            "battery_pct",
            "charging",
            "cpu_pct",
            "ram_pct",
            "ram_total_gb",
            "ram_used_gb",
            "storage_total_gb",
            "storage_free_gb",
            "storage_free_pct",
            "temperature",
            "network_connected",
            "battery_critical",
            "storage_critical",
        ]

        for key in required_keys:
            if key not in status:
                log.error(f"HardwareMonitor self_test failed: missing key '{key}'")
                return False

        throttle = hw.should_throttle()
        if not isinstance(throttle, bool):
            log.error("HardwareMonitor self_test failed: should_throttle() did not return bool")
            return False

        log.info(f"HardwareMonitor self_test passed. Status sample: {status}")
        return True
    except Exception as e:
        log.error(f"HardwareMonitor self_test exception: {e}")
        return False


if __name__ == "__main__":
    success = self_test()
    if success:
        print("HardwareMonitor self-test: PASSED")
        sys.exit(0)
    else:
        print("HardwareMonitor self-test: FAILED")
        sys.exit(1)
