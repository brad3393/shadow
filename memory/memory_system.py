"""
Shadow Memory System.

Provides persistent local memory storage in JSON files organized by category.
Implements the BaseMemory interface from core.base.
"""

import json
import os
import re
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# Ensure shadow root directory is in sys.path when module is executed directly
_shadow_root = Path(__file__).resolve().parent.parent
if str(_shadow_root) not in sys.path:
    sys.path.insert(0, str(_shadow_root))

try:
    import fcntl
except ImportError:
    fcntl = None  # Non-Unix fallback

from config.config import MEMORY_DIR
from core.base import BaseMemory
from logging.logger import ShadowLogger

log = ShadowLogger.get("shadow.memory")

DEFAULT_CATEGORIES = [
    "user_info",
    "instructions",
    "projects",
    "tasks",
    "knowledge",
    "learned_procedures",
    "tool_descriptions",
    "agent_capabilities",
    "previous_successes",
    "previous_failures",
]


class FileLock:
    """Context manager for process-safe file locking using fcntl where available."""

    def __init__(self, lock_path: Path):
        self.lock_file_path = lock_path.with_suffix(lock_path.suffix + ".lock")
        self._fd = None

    def __enter__(self):
        if fcntl is not None:
            try:
                self._fd = open(self.lock_file_path, "w")
                fcntl.flock(self._fd, fcntl.LOCK_EX)
            except (OSError, IOError):
                self._fd = None
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._fd is not None:
            try:
                fcntl.flock(self._fd, fcntl.LOCK_UN)
                self._fd.close()
            except (OSError, IOError):
                pass
            try:
                if self.lock_file_path.exists():
                    self.lock_file_path.unlink()
            except (OSError, IOError):
                pass


class MemorySystem(BaseMemory):
    """
    Persistent local memory system for Shadow.
    Stores entries as JSON files organized by category in MEMORY_DIR.
    Thread-safe and process-safe with file locking.
    """

    def __init__(self, memory_dir: Optional[Path] = None):
        self.memory_dir = Path(memory_dir) if memory_dir else MEMORY_DIR
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize_categories()

    def _initialize_categories(self):
        """Ensure standard category JSON files exist."""
        for category in DEFAULT_CATEGORIES:
            cat_file = self._get_category_file(category)
            if not cat_file.exists():
                self._write_category_data(cat_file, {})

    def _sanitize_category(self, category: str) -> str:
        """Sanitize category name for safe filename usage."""
        if not category:
            category = "general"
        sanitized = re.sub(r"[^\w\-]", "_", category.strip().lower())
        return sanitized or "general"

    def _get_category_file(self, category: str) -> Path:
        cat_name = self._sanitize_category(category)
        return self.memory_dir / f"{cat_name}.json"

    def _read_category_data(self, cat_file: Path) -> Dict[str, dict]:
        """Read data dictionary from category JSON file."""
        if not cat_file.exists():
            return {}
        try:
            with open(cat_file, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    return {}
                data = json.loads(content)
                if isinstance(data, dict):
                    return data
                return {}
        except Exception as e:
            log.warning(f"Error reading memory file {cat_file}: {e}")
            return {}

    def _write_category_data(self, cat_file: Path, data: Dict[str, dict]) -> bool:
        """Write data dictionary to category JSON file atomically."""
        try:
            tmp_file = cat_file.with_suffix(".json.tmp")
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=self._json_serializer)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_file, cat_file)
            return True
        except Exception as e:
            log.error(f"Error writing memory file {cat_file}: {e}")
            return False

    @staticmethod
    def _json_serializer(obj: Any) -> Any:
        if hasattr(obj, "to_dict") and callable(obj.to_dict):
            return obj.to_dict()
        if hasattr(obj, "__dict__"):
            return obj.__dict__
        return str(obj)

    def store(self, category: str, key: str, value: Any) -> bool:
        """
        Store a key-value record under specified category.

        Args:
            category: Memory category name (e.g., 'user_info', 'tasks')
            key: Unique key within the category
            value: Data to store (JSON serializable or handled by serializer)

        Returns:
            bool: True on success, False on failure
        """
        if not category or not key:
            log.warning("Store operation failed: category and key must be non-empty.")
            return False

        cat_file = self._get_category_file(category)
        sanitized_cat = self._sanitize_category(category)

        with self._lock:
            with FileLock(cat_file):
                data = self._read_category_data(cat_file)
                data[key] = {
                    "key": key,
                    "category": sanitized_cat,
                    "value": value,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
                success = self._write_category_data(cat_file, data)
                if success:
                    log.debug(f"Stored key '{key}' in category '{sanitized_cat}'")
                return success

    def retrieve(self, category: str, key: str) -> Optional[Any]:
        """
        Retrieve a value stored under key in specified category.

        Args:
            category: Memory category name
            key: Key to lookup

        Returns:
            Stored value if found, None otherwise
        """
        if not category or not key:
            return None

        cat_file = self._get_category_file(category)

        with self._lock:
            with FileLock(cat_file):
                data = self._read_category_data(cat_file)
                entry = data.get(key)
                if entry is None:
                    return None
                if isinstance(entry, dict) and "value" in entry:
                    return entry["value"]
                return entry

    def list_category(self, category: str) -> List[dict]:
        """
        List all records in a category.

        Args:
            category: Memory category name

        Returns:
            List of record dicts, each containing 'key', 'category', 'value', etc.
        """
        if not category:
            return []

        cat_file = self._get_category_file(category)

        with self._lock:
            with FileLock(cat_file):
                data = self._read_category_data(cat_file)
                results = []
                for k, v in data.items():
                    if isinstance(v, dict) and "key" in v and "value" in v:
                        results.append(v)
                    else:
                        results.append({
                            "key": k,
                            "category": self._sanitize_category(category),
                            "value": v,
                        })
                return results

    def search(self, category: str, query: str) -> List[dict]:
        """
        Search for query string in specified category or across all categories if category is wildcard/empty.

        Args:
            category: Category to search or '', '*', 'all' for all categories
            query: String query to search for

        Returns:
            List of matching record dicts
        """
        if not query:
            return []

        q = query.lower().strip()
        search_all = not category or category.strip().lower() in ("", "*", "all")

        files_to_search: List[Path] = []
        with self._lock:
            if search_all:
                files_to_search = list(self.memory_dir.glob("*.json"))
            else:
                cat_file = self._get_category_file(category)
                if cat_file.exists():
                    files_to_search = [cat_file]

        results = []
        for cat_file in files_to_search:
            if cat_file.name.endswith(".tmp") or cat_file.name.endswith(".lock"):
                continue

            with self._lock:
                with FileLock(cat_file):
                    data = self._read_category_data(cat_file)
                    for k, record in data.items():
                        if not isinstance(record, dict) or "value" not in record:
                            record_dict = {
                                "key": k,
                                "category": cat_file.stem,
                                "value": record,
                            }
                        else:
                            record_dict = record

                        val_str = json.dumps(record_dict.get("value", ""), ensure_ascii=False, default=self._json_serializer).lower()
                        key_str = str(record_dict.get("key", "")).lower()
                        cat_str = str(record_dict.get("category", "")).lower()

                        if q in key_str or q in val_str or q in cat_str:
                            results.append(record_dict)

        return results

    def delete(self, category: str, key: str) -> bool:
        """
        Delete a key from specified category.

        Args:
            category: Memory category name
            key: Key to delete

        Returns:
            bool: True if key existed and was deleted, False otherwise
        """
        if not category or not key:
            return False

        cat_file = self._get_category_file(category)

        with self._lock:
            with FileLock(cat_file):
                data = self._read_category_data(cat_file)
                if key in data:
                    del data[key]
                    self._write_category_data(cat_file, data)
                    log.debug(f"Deleted key '{key}' from category '{category}'")
                    return True
                return False

    def get_context(self, task_description: str) -> dict:
        """
        Pull relevant memories for a given task description to provide context for execution.

        Args:
            task_description: The description or title of the task to gather context for.

        Returns:
            dict containing relevant memories structured by category and summarized.
        """
        if not task_description:
            task_description = ""

        task_words = [w.lower() for w in re.findall(r"\w+", task_description) if len(w) > 2]
        stop_words = {
            "the", "and", "for", "that", "this", "with", "from", "are", "was", "were",
            "have", "has", "had", "been", "will", "would", "should", "could", "can",
            "you", "your", "them", "they", "our", "all", "any", "some", "not", "but",
        }
        filtered_words = [w for w in task_words if w not in stop_words]

        context_by_category: Dict[str, List[dict]] = {
            "user_info": self.list_category("user_info"),
            "instructions": [],
            "learned_procedures": [],
            "previous_successes": [],
            "previous_failures": [],
            "tool_descriptions": [],
            "agent_capabilities": [],
            "knowledge": [],
            "projects": [],
            "tasks": [],
        }

        relevant_records: List[dict] = []
        seen_keys: Set[str] = set()

        def add_record(rec: dict):
            unique_id = f"{rec.get('category')}:{rec.get('key')}"
            if unique_id not in seen_keys:
                seen_keys.add(unique_id)
                relevant_records.append(rec)
                cat = rec.get("category", "")
                if cat in context_by_category and rec not in context_by_category[cat]:
                    context_by_category[cat].append(rec)

        if filtered_words:
            for word in filtered_words[:10]:
                matches = self.search("all", word)
                for match in matches:
                    add_record(match)

        instructions = self.list_category("instructions")
        for inst in instructions:
            add_record(inst)

        for cat in ("previous_successes", "previous_failures"):
            for rec in self.list_category(cat):
                rec_str = json.dumps(rec, ensure_ascii=False, default=self._json_serializer).lower()
                if any(w in rec_str for w in filtered_words):
                    add_record(rec)

        summary_lines = []
        if context_by_category["user_info"]:
            summary_lines.append(f"User Info ({len(context_by_category['user_info'])} items)")
        if relevant_records:
            summary_lines.append(f"Relevant Memories ({len(relevant_records)} items)")

        return {
            "task": task_description,
            "user_info": context_by_category["user_info"],
            "instructions": context_by_category["instructions"],
            "learned_procedures": context_by_category["learned_procedures"],
            "previous_successes": context_by_category["previous_successes"],
            "previous_failures": context_by_category["previous_failures"],
            "tool_descriptions": context_by_category["tool_descriptions"],
            "agent_capabilities": context_by_category["agent_capabilities"],
            "knowledge": context_by_category["knowledge"],
            "relevant_memories": relevant_records,
            "summary": "; ".join(summary_lines) if summary_lines else "No relevant context found.",
        }


def self_test() -> bool:
    """Run a self-test of the MemorySystem."""
    import shutil
    import tempfile

    temp_dir = Path(tempfile.mkdtemp(prefix="shadow_mem_test_"))
    try:
        mem = MemorySystem(memory_dir=temp_dir)

        # 1. Check default category files created
        for cat in DEFAULT_CATEGORIES:
            cat_file = temp_dir / f"{cat}.json"
            assert cat_file.exists(), f"Category file {cat}.json was not created"

        # 2. Test Store and Retrieve
        assert mem.store("user_info", "name", "ShadowUser"), "Store failed"
        assert mem.retrieve("user_info", "name") == "ShadowUser", "Retrieve failed"

        # 3. Test storing complex object
        complex_val = {"prefer_dark_mode": True, "language": "Python", "roles": ["admin"]}
        assert mem.store("user_info", "settings", complex_val), "Store complex object failed"
        assert mem.retrieve("user_info", "settings") == complex_val, "Retrieve complex object failed"

        # 4. Test list_category
        items = mem.list_category("user_info")
        assert len(items) == 2, f"Expected 2 items in user_info, got {len(items)}"

        # 5. Test search within category and all
        mem.store("learned_procedures", "git_commit", "Use git commit -m to commit changes")
        mem.store("previous_successes", "task_101", {"task": "Build python module", "agent": "coding"})

        git_matches = mem.search("learned_procedures", "git")
        assert len(git_matches) >= 1, "Search in specific category failed"

        python_matches = mem.search("all", "python")
        assert len(python_matches) >= 2, f"Search across all failed, got {len(python_matches)}"

        # 6. Test get_context
        ctx = mem.get_context("Build a python module and commit to git")
        assert ctx["task"] == "Build a python module and commit to git"
        assert len(ctx["relevant_memories"]) >= 1, "get_context failed to find relevant memories"

        # 7. Test delete
        assert mem.delete("user_info", "name"), "Delete failed"
        assert mem.retrieve("user_info", "name") is None, "Retrieve after delete should be None"
        assert len(mem.list_category("user_info")) == 1, "list_category count after delete failed"

        print("MemorySystem self_test passed successfully.")
        return True
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    success = self_test()
    if success:
        print("Self test completed with SUCCESS!")
    else:
        print("Self test FAILED!")
