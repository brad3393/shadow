"""
Shadow — Central Configuration
All system-wide settings live here. Components read from this, never hardcode.
"""
import os
from pathlib import Path

# ─── Paths ────────────────────────────────────────────────────────
SHADOW_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR    = SHADOW_ROOT / "shadow_data"
MEMORY_DIR  = DATA_DIR / "memory"
TASKS_DIR   = DATA_DIR / "tasks"
VAULT_DIR   = DATA_DIR / "vault"
LOGS_DIR    = DATA_DIR / "logs"
CHECKPOINTS = DATA_DIR / "checkpoints"
KNOWLEDGE_DIR = DATA_DIR / "knowledge"

# ─── Ollama ────────────────────────────────────────────────────────
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "120"))

# ─── Execution Limits ─────────────────────────────────────────────
MAX_CORRECTION_ATTEMPTS = 3
MAX_AUTONOMOUS_ITERATIONS = 10
SANDBOX_TIMEOUT_SECONDS = 30

# ─── Safety ────────────────────────────────────────────────────────
REQUIRE_APPROVAL_FOR = {
    "delete_important_files",
    "install_software",
    "change_security_settings",
    "access_sensitive_dirs",
    "modify_system_config",
    "send_external",
    "irreversible_ops",
}

# ─── Hardware Thresholds ──────────────────────────────────────────
BATTERY_CRITICAL = 15   # percent
STORAGE_CRITICAL  = 5    # percent free
CPU_THROTTLE      = 90   # percent

# ─── Ensure dirs exist ────────────────────────────────────────────
for d in [DATA_DIR, MEMORY_DIR, TASKS_DIR, VAULT_DIR, LOGS_DIR, CHECKPOINTS, KNOWLEDGE_DIR]:
    d.mkdir(parents=True, exist_ok=True)
