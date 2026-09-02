"""
Shadow Capability Registry
Registers, lists, and queries capabilities (agents and tools) across the Shadow network.
Persists registry state in DATA_DIR/capability_registry.json.
"""
import json
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional

# Ensure parent directory is in sys.path
shadow_dir = str(Path(__file__).resolve().parent.parent)
if shadow_dir not in sys.path:
    sys.path.insert(0, shadow_dir)

from config.config import DATA_DIR
from logging.logger import ShadowLogger

log = ShadowLogger.get("shadow.registry")


class CapabilityRegistry:
    """Registry for managing agent and tool capabilities."""

    def __init__(self, registry_file: Optional[Path] = None):
        self.registry_file = registry_file or (DATA_DIR / "capability_registry.json")
        self.agents: Dict[str, Dict[str, Any]] = {}
        self.tools: Dict[str, Dict[str, Any]] = {}

        # Auto-load existing registry if present
        if self.registry_file.exists():
            self.load()

    def register_agent(self, name: str, description: str) -> bool:
        """Register or update an agent capability."""
        if not name or not isinstance(name, str):
            log.error("Invalid agent name provided")
            return False

        agent_entry = {
            "type": "agent",
            "name": name,
            "description": description or "",
        }
        self.agents[name] = agent_entry
        log.info(f"Registered agent capability: '{name}'")
        self.save()
        return True

    def register_tool(self, name: str, description: str, path: str) -> bool:
        """Register or update a tool capability."""
        if not name or not isinstance(name, str):
            log.error("Invalid tool name provided")
            return False

        tool_entry = {
            "type": "tool",
            "name": name,
            "description": description or "",
            "path": path or "",
        }
        self.tools[name] = tool_entry
        log.info(f"Registered tool capability: '{name}' at '{path}'")
        self.save()
        return True

    def unregister(self, name: str) -> bool:
        """Unregister an agent or tool by name."""
        removed = False
        if name in self.agents:
            del self.agents[name]
            removed = True
            log.info(f"Unregistered agent capability: '{name}'")
        elif name in self.tools:
            del self.tools[name]
            removed = True
            log.info(f"Unregistered tool capability: '{name}'")

        if removed:
            self.save()
            return True

        log.warning(f"Failed to unregister '{name}': not found in registry")
        return False

    def list_capabilities(self) -> List[Dict[str, Any]]:
        """Return a list of all registered capabilities (agents + tools)."""
        return list(self.agents.values()) + list(self.tools.values())

    def get_agent(self, name: str) -> Optional[Dict[str, Any]]:
        """Retrieve registered agent details by name."""
        return self.agents.get(name)

    def get_tool(self, name: str) -> Optional[Dict[str, Any]]:
        """Retrieve registered tool details by name."""
        return self.tools.get(name)

    def has_capability(self, capability: str) -> bool:
        """
        Search registered capabilities for keyword match in description or name.
        Returns True if a match is found.
        """
        if not capability or not isinstance(capability, str):
            return False

        query = capability.strip().lower()
        if not query:
            return False

        for cap in self.list_capabilities():
            desc = cap.get("description", "").lower()
            name = cap.get("name", "").lower()
            if query in desc or query in name:
                return True

        return False

    def save(self) -> bool:
        """Save registry contents to capability_registry.json."""
        try:
            data = {
                "agents": self.agents,
                "tools": self.tools,
            }
            self.registry_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.registry_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            log.debug(f"CapabilityRegistry saved to {self.registry_file}")
            return True
        except Exception as e:
            log.error(f"Failed to save CapabilityRegistry: {e}")
            return False

    def load(self) -> bool:
        """Load registry contents from capability_registry.json."""
        if not self.registry_file.exists():
            log.debug(f"Registry file {self.registry_file} does not exist.")
            return False

        try:
            with open(self.registry_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.agents = data.get("agents", {})
            self.tools = data.get("tools", {})
            log.debug(
                f"CapabilityRegistry loaded from {self.registry_file} "
                f"({len(self.agents)} agents, {len(self.tools)} tools)"
            )
            return True
        except Exception as e:
            log.error(f"Failed to load CapabilityRegistry: {e}")
            return False


def self_test() -> bool:
    """Self-test for CapabilityRegistry component validation."""
    log.info("Running CapabilityRegistry self_test...")
    test_file = DATA_DIR / "test_capability_registry.json"
    if test_file.exists():
        test_file.unlink()

    try:
        registry = CapabilityRegistry(registry_file=test_file)

        # 1. Register Agent
        ok_agent = registry.register_agent("test_coder", "Generates Python code")
        if not ok_agent or registry.get_agent("test_coder") is None:
            log.error("Failed register_agent check")
            return False

        # 2. Register Tool
        ok_tool = registry.register_tool(
            "file_writer", "Writes text to files", "/tools/writer.py"
        )
        if not ok_tool or registry.get_tool("file_writer") is None:
            log.error("Failed register_tool check")
            return False

        # 3. List capabilities
        caps = registry.list_capabilities()
        if len(caps) != 2:
            log.error(f"Failed list_capabilities count check: expected 2, got {len(caps)}")
            return False

        # 4. Search capability keyword
        if not registry.has_capability("python"):
            log.error("Failed has_capability('python') check")
            return False

        if not registry.has_capability("writer"):
            log.error("Failed has_capability('writer') check")
            return False

        if registry.has_capability("nonexistent_keyword_xyz"):
            log.error("Failed has_capability negative check")
            return False

        # 5. Persistence save & load
        if not registry.save():
            log.error("Failed save() check")
            return False

        new_reg = CapabilityRegistry(registry_file=test_file)
        if not new_reg.load():
            log.error("Failed load() check")
            return False

        if not new_reg.get_agent("test_coder") or not new_reg.get_tool("file_writer"):
            log.error("Failed reloaded registry check")
            return False

        # 6. Unregister
        if not registry.unregister("test_coder"):
            log.error("Failed unregister agent check")
            return False

        if registry.get_agent("test_coder") is not None:
            log.error("Agent still present after unregister")
            return False

        if not registry.unregister("file_writer"):
            log.error("Failed unregister tool check")
            return False

        if registry.get_tool("file_writer") is not None:
            log.error("Tool still present after unregister")
            return False

        log.info("CapabilityRegistry self_test passed.")
        return True
    except Exception as e:
        log.error(f"CapabilityRegistry self_test exception: {e}")
        return False
    finally:
        if test_file.exists():
            test_file.unlink()


if __name__ == "__main__":
    success = self_test()
    if success:
        print("CapabilityRegistry self-test: PASSED")
        sys.exit(0)
    else:
        print("CapabilityRegistry self-test: FAILED")
        sys.exit(1)
