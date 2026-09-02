"""
Shadow Task Manager — Task Queue and Persistence.

Provides thread-safe, file-locked task management with priority scheduling,
dependency tracking, and persistent storage.
"""
import copy
import fcntl
import json
import os
import sys
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure shadow root directory is in sys.path
shadow_root = Path(__file__).resolve().parent.parent
if str(shadow_root) not in sys.path:
    sys.path.insert(0, str(shadow_root))

from config.config import TASKS_DIR
from logging.logger import ShadowLogger

log = ShadowLogger.get("shadow.tasks")

# Priority ranking (lower index = higher priority)
PRIORITY_ORDER = {
    "critical": 0,
    "high": 1,
    "normal": 2,
    "low": 3,
}

VALID_STATUSES = {"pending", "in_progress", "completed", "failed", "blocked"}


@contextmanager
def _file_lock(lock_path: Path):
    """File lock context manager for cross-process synchronization."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    f = open(lock_path, "w")
    try:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
        f.close()


class TaskManager:
    """Manages tasks with file persistence and thread/process lock protection."""

    def __init__(self, tasks_file: Optional[Path] = None):
        if tasks_file:
            self.tasks_file = Path(tasks_file)
        else:
            self.tasks_file = TASKS_DIR / "tasks.json"

        self.lock_file = self.tasks_file.with_suffix(".lock")
        self._lock = threading.RLock()

    def _load_tasks(self) -> Dict[str, dict]:
        """Load tasks from JSON storage."""
        if not self.tasks_file.exists():
            return {}
        try:
            with open(self.tasks_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
                elif isinstance(data, list):
                    # Convert list to dict if legacy format
                    return {t["id"]: t for t in data if isinstance(t, dict) and "id" in t}
                return {}
        except Exception as e:
            log.error(f"Failed to load tasks from {self.tasks_file}: {e}")
            return {}

    def _save_tasks(self, tasks: Dict[str, dict]) -> None:
        """Save tasks atomically to JSON storage."""
        try:
            self.tasks_file.parent.mkdir(parents=True, exist_ok=True)
            tmp_file = self.tasks_file.with_suffix(".tmp")
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(tasks, f, indent=2)
            os.replace(tmp_file, self.tasks_file)
        except Exception as e:
            log.error(f"Failed to save tasks to {self.tasks_file}: {e}")

    @contextmanager
    def _read_transaction(self):
        """Context manager for thread-safe and process-safe reads."""
        with self._lock:
            with _file_lock(self.lock_file):
                tasks = self._load_tasks()
                yield tasks

    @contextmanager
    def _write_transaction(self):
        """Context manager for thread-safe and process-safe writes."""
        with self._lock:
            with _file_lock(self.lock_file):
                tasks = self._load_tasks()
                yield tasks
                self._save_tasks(tasks)

    def create_task(
        self,
        description: str,
        required_agent: str,
        priority: str = "normal",
        dependencies: Optional[List[str]] = None,
    ) -> dict:
        """
        Create a new task and persist it.

        Returns:
            dict: The created task dictionary including its generated UUID.
        """
        p_clean = str(priority).lower() if priority else "normal"
        if p_clean not in PRIORITY_ORDER:
            p_clean = "normal"

        dep_list = list(dependencies) if dependencies else []
        task_id = str(uuid.uuid4())
        created_iso = datetime.now().isoformat()

        task = {
            "id": task_id,
            "description": description,
            "priority": p_clean,
            "status": "pending",
            "required_agent": required_agent,
            "dependencies": dep_list,
            "created_time": created_iso,
            "completion_time": None,
            "result": None,
            "error": None,
            "error_info": None,
        }

        with self._write_transaction() as tasks:
            tasks[task_id] = task

        log.info(f"Created task {task_id} ({p_clean}): {description[:40]}")
        return copy.deepcopy(task)

    def get_task(self, task_id: str) -> Optional[dict]:
        """Retrieve a task by ID."""
        with self._read_transaction() as tasks:
            task = tasks.get(task_id)
            return copy.deepcopy(task) if task else None

    def update_task(self, task_id: str, **fields) -> dict:
        """Update task fields and persist changes."""
        with self._write_transaction() as tasks:
            if task_id not in tasks:
                raise KeyError(f"Task {task_id} not found.")

            task = tasks[task_id]

            # Auto-set completion_time when completed or failed
            new_status = fields.get("status")
            if new_status in ("completed", "failed") and "completion_time" not in fields:
                fields["completion_time"] = datetime.now().isoformat()

            # Sync error and error_info
            if "error" in fields and "error_info" not in fields:
                fields["error_info"] = fields["error"]
            elif "error_info" in fields and "error" not in fields:
                fields["error"] = fields["error_info"]

            for key, value in fields.items():
                task[key] = value

            log.info(f"Updated task {task_id}: fields {list(fields.keys())}")
            return copy.deepcopy(task)

    def get_next_task(self) -> Optional[dict]:
        """
        Get the highest priority pending task whose dependencies are met.

        Priority order: critical > high > normal > low.
        Tie breaker: oldest created_time.
        """
        with self._read_transaction() as tasks:
            eligible = []
            for t_id, task in tasks.items():
                if task.get("status") != "pending":
                    continue

                # Check if all dependencies are completed
                deps = task.get("dependencies", [])
                deps_satisfied = True
                for dep_id in deps:
                    dep_task = tasks.get(dep_id)
                    if not dep_task or dep_task.get("status") != "completed":
                        deps_satisfied = False
                        break

                if deps_satisfied:
                    eligible.append(task)

            if not eligible:
                return None

            eligible.sort(
                key=lambda x: (
                    PRIORITY_ORDER.get(str(x.get("priority")).lower(), 2),
                    x.get("created_time", ""),
                )
            )

            return copy.deepcopy(eligible[0])

    def list_tasks(self, status: Optional[str] = None) -> List[dict]:
        """List tasks, optionally filtered by status."""
        with self._read_transaction() as tasks:
            if status is None:
                return copy.deepcopy(list(tasks.values()))
            return [
                copy.deepcopy(t)
                for t in tasks.values()
                if t.get("status") == status
            ]

    def count_tasks(self, status: Optional[str] = None) -> int:
        """Count total tasks or tasks matching status."""
        with self._read_transaction() as tasks:
            if status is None:
                return len(tasks)
            return sum(1 for t in tasks.values() if t.get("status") == status)

    def delete_task(self, task_id: str) -> bool:
        """Delete a task by ID."""
        with self._write_transaction() as tasks:
            if task_id in tasks:
                del tasks[task_id]
                log.info(f"Deleted task {task_id}")
                return True
            return False

    def clear_completed(self) -> bool:
        """Clear all completed and failed tasks."""
        with self._write_transaction() as tasks:
            to_remove = [
                t_id
                for t_id, task in tasks.items()
                if task.get("status") in ("completed", "failed")
            ]
            for t_id in to_remove:
                del tasks[t_id]
            log.info(f"Cleared {len(to_remove)} completed/failed tasks.")
            return True


def self_test() -> bool:
    """Self-test for TaskManager functionality."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp_dir:
        test_file = Path(tmp_dir) / "test_tasks.json"
        tm = TaskManager(tasks_file=test_file)

        # 1. Create tasks
        t1 = tm.create_task("First task", "agent1", priority="low")
        t2 = tm.create_task("Second task (critical)", "agent2", priority="critical", dependencies=[t1["id"]])
        t3 = tm.create_task("Third task (high)", "agent1", priority="high")

        assert t1["id"] is not None
        assert t1["priority"] == "low"
        assert t1["status"] == "pending"

        # 2. Get next task -> should be t3 because t2 depends on t1 (not completed yet), and t3 (high) > t1 (low)
        next_task = tm.get_next_task()
        assert next_task is not None
        assert next_task["id"] == t3["id"]

        # 3. Update task t1 status to completed
        tm.update_task(t1["id"], status="completed", result="Done!")
        t1_updated = tm.get_task(t1["id"])
        assert t1_updated["status"] == "completed"
        assert t1_updated["completion_time"] is not None
        assert t1_updated["result"] == "Done!"

        # 4. Get next task -> should now be t2 (critical and dependency t1 is completed)
        next_task_2 = tm.get_next_task()
        assert next_task_2 is not None
        assert next_task_2["id"] == t2["id"]

        # 5. List and count
        assert tm.count_tasks() == 3
        assert tm.count_tasks("pending") == 2
        assert len(tm.list_tasks("pending")) == 2

        # 6. Delete task t3
        assert tm.delete_task(t3["id"]) is True
        assert tm.get_task(t3["id"]) is None
        assert tm.count_tasks() == 2

        # 7. Clear completed
        assert tm.clear_completed() is True
        assert tm.get_task(t1["id"]) is None
        assert tm.count_tasks() == 1  # Only t2 remains

    return True


if __name__ == "__main__":
    print("Running TaskManager self-test...")
    if self_test():
        print("TaskManager self-test PASSED!")
    else:
        print("TaskManager self-test FAILED!")
