"""
Shadow base interfaces. Every module implements these contracts.
"""
from abc import ABC, abstractmethod
from typing import Any, Optional, Dict, List


class BaseAgent(ABC):
    """Every expert agent inherits from this."""
    name: str = "base"
    description: str = ""

    @abstractmethod
    def can_handle(self, task_description: str) -> bool:
        """Return True if this agent is suited for the task."""
        ...

    @abstractmethod
    def execute(self, task: dict) -> dict:
        """Execute a task dict, return a result dict with 'success', 'output', 'error'."""
        ...


class BaseMemory(ABC):
    """Memory backends implement this."""

    @abstractmethod
    def store(self, category: str, key: str, value: Any) -> bool:
        ...

    @abstractmethod
    def retrieve(self, category: str, key: str) -> Optional[Any]:
        ...

    @abstractmethod
    def search(self, category: str, query: str) -> List[dict]:
        ...

    @abstractmethod
    def list_category(self, category: str) -> List[dict]:
        ...

    @abstractmethod
    def delete(self, category: str, key: str) -> bool:
        ...


class BaseTool(ABC):
    """Tools in the Vault implement this."""
    name: str = "base_tool"
    description: str = ""

    @abstractmethod
    def run(self, **kwargs) -> dict:
        ...


class GuardianCheck(ABC):
    """Guardian hooks for pre/post execution checks."""
    @abstractmethod
    def pre_check(self, action: str, context: dict) -> tuple[bool, str]:
        """Return (allowed, reason)."""
        ...

    @abstractmethod
    def post_check(self, action: str, result: dict) -> tuple[bool, str]:
        """Return (safe, reason)."""
        ...
