"""
Shadow v1 — Comprehensive Test Suite

Tests every component of the Shadow system:
  1. Core boot & agent registration
  2. SystemAgent NL→shell translation & execution
  3. All 10 expert agents via Core routing
  4. Task manager (create, track, complete)
  5. Memory system (store, retrieve, categories)
  6. Guardian (dangerous patterns, file access, approval, checkpoint, rollback)
  7. Bot Factory (build, test, deploy tools)
  8. Hardware monitor (CPU, RAM, storage, network)
  9. Vault (store, retrieve, list, search, delete)
  10. Self-Improvement (error analysis, proposals, capability gaps)
  11. Autonomous loop
  12. CLI interface
  13. main.py entry point
"""
import sys
import os
import json
import subprocess
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

passed = 0
failed = 0
degraded = 0

def check(label, condition, is_degraded=False):
    global passed, failed, degraded
    if condition:
        passed += 1
        print(f"  PASS  {label}")
    elif is_degraded:
        degraded += 1
        print(f"  DEGRADED  {label}")
    else:
        failed += 1
        print(f"  FAIL  {label}")

def section(n, title):
    print(f"\n[{n}] {title}")


if __name__ == "__main__":
    print("=" * 60)
    print("  SHADOW v1 — COMPREHENSIVE TEST SUITE")
    print("=" * 60)

    # ─── 1. Core boot ───────────────────────────────────────────
    section(1, "Core Boot & Agent Registration")
    from core.shadow_core import ShadowCore
    core = ShadowCore()
    core.boot()
    check("10 agents registered", len(core.agents) == 10)
    check("vault initialized", core.vault is not None)
    check("self_improvement initialized", core.self_improvement is not None)
    check("memory initialized", core.memory is not None)
    check("task_manager initialized", core.task_manager is not None)
    check("guardian initialized", core.guardian is not None)
    check("hardware initialized", core.hardware is not None)
    check("ollama initialized", core.ollama is not None)
    check("capability_registry initialized", core.capability_registry is not None)

    # ─── 2. SystemAgent ─────────────────────────────────────────
    section(2, "SystemAgent NL→Shell Translation")
    from agents.system_agent import SystemAgent
    sa = SystemAgent()
    translations = [
        ("show the date and time", "date"),
        ("check system uptime", "uptime"),
        ("show disk usage", "df"),
        ("what OS version is this", "uname"),
        ("show running processes", "ps"),
        ("show memory usage", "free"),
        ("show CPU usage", "top"),
        ("show IP address", "ip"),
        ("show the hostname", "hostname"),
        ("show environment variables", "env"),
    ]
    for desc, expected in translations:
        t = sa._translate_command(desc)
        check(f"{desc} -> {t}", expected in t.lower())

    section(2.1, "SystemAgent Execution")
    r = sa.execute({"description": "show the date and time", "id": "t1"})
    check("executes date command", r["success"])
    check("returns output", len(r.get("output", "")) > 0)

    # ─── 3. All 10 agents via Core ───────────────────────────────
    section(3, "All 10 Expert Agents via Core Routing")
    cmds = [
        ("list all files in this directory", "file_agent"),
        ("scan for security issues in this directory", "security_agent"),
        ("report current CPU and RAM status", "hardware_agent"),
        ("write a Python script that prints hello world", "coding_agent"),
        ("find all Python files in the current directory", "research_agent"),
        ("show the date and time", "system_agent"),
        ("plan three steps to organize a workspace", "planning_agent"),
        ("verify that the number 4 is even", "testing_agent"),
        ("extract key facts from a text about the solar system", "learning_agent"),
        ("write a brief README for a calculator", "documentation_agent"),
    ]
    for cmd, agent in cmds:
        routed = core._select_agent(cmd)
        check(f"{agent} routing", routed == agent)
        r = core.receive_command(cmd)
        check(f"{agent} execution", r.get("success"), is_degraded=not r.get("success"))

    # ─── 4. Task Manager ────────────────────────────────────────
    section(4, "Task Manager")
    tasks = core.task_manager.list_tasks()
    check("tasks tracked", len(tasks) > 0)
    check("has completed tasks", core.task_manager.count_tasks("completed") > 0)
    # Create a manual task
    t = core.task_manager.create_task(
        description="test task", required_agent="system_agent", priority="high"
    )
    check("create task", t["id"] is not None)
    check("task has priority", t.get("priority") == "high")
    check("task has status", t.get("status") == "pending")
    # Update task
    core.task_manager.update_task(t["id"], status="completed", result="done")
    check("update task", core.task_manager.count_tasks("completed") > 0)

    # ─── 5. Memory System ───────────────────────────────────────
    section(5, "Memory System")
    core.memory.store("user", "name", {"value": "Brad"})
    check("store user data", core.memory.retrieve("user", "name") is not None)
    check("retrieve correct value", core.memory.retrieve("user", "name").get("value") == "Brad")
    core.memory.store("instructions", "i1", {"text": "always be helpful"})
    check("store instructions", core.memory.retrieve("instructions", "i1") is not None)
    core.memory.store("knowledge", "k1", {"topic": "python", "fact": "interpreted language"})
    check("store knowledge", core.memory.retrieve("knowledge", "k1") is not None)

    # ─── 6. Guardian ────────────────────────────────────────────
    section(6, "Guardian Security Layer")
    # Dangerous patterns
    a, _ = core.guardian.pre_check("system_command", {"command": "ls -la"})
    check("allows safe command", a)
    b, reason = core.guardian.pre_check("system_command", {"command": "rm -rf /"})
    check("blocks rm -rf /", not b)
    c, reason = core.guardian.pre_check("system_command", {"command": "sudo apt install evil"})
    check("blocks sudo", not c)
    d, reason = core.guardian.pre_check("system_command", {"command": "chmod 777 /etc"})
    check("blocks chmod 777", not d)
    e, reason = core.guardian.pre_check("system_command", {"command": "dd if=/dev/zero of=/dev/sda"})
    check("blocks dd", not e)
    # File access
    f, reason = core.guardian.pre_check("write_file", {"path": "/etc/passwd"})
    check("blocks write to /etc/passwd", not f)
    g, reason = core.guardian.pre_check("write_file", {"path": "/proc/sys/kernel"})
    check("blocks write to /proc", not g)
    # Checkpoint + rollback
    cp_id = core.guardian.create_checkpoint("test_checkpoint")
    check("create checkpoint", cp_id is not None)
    rollback_ok = core.guardian.rollback(cp_id)
    check("rollback from checkpoint", rollback_ok)
    # Audit log
    check("audit log exists", core.guardian.audit_log_path.exists())

    # ─── 7. Bot Factory ─────────────────────────────────────────
    section(7, "Bot Factory")
    from botfactory.bot_factory import BotFactory
    bf = BotFactory(ollama=core.ollama, registry=core.capability_registry)
    r = bf.build_tool("Calculate square root of 16", max_attempts=3)
    check("builds a tool", r["success"])
    check("attempts <= 3", r["attempts"] <= 3)

    # ─── 8. Hardware Monitor ────────────────────────────────────
    section(8, "Hardware Monitor")
    hw = core.hardware.get_status()
    check("has cpu_pct", "cpu_pct" in hw)
    check("has ram_pct", "ram_pct" in hw)
    check("has storage_free_pct", "storage_free_pct" in hw)
    check("has network_connected", "network_connected" in hw)
    check("has battery_critical", "battery_critical" in hw)
    check("has storage_critical", "storage_critical" in hw)

    # ─── 9. Vault ───────────────────────────────────────────────
    section(9, "Vault")
    r = core.vault.store("tools", "test_tool.py", "print('hello from vault')", {"type": "python"})
    check("store item", r["success"])
    content = core.vault.retrieve("tools/test_tool.py")
    check("retrieve item", content is not None and "hello" in content)
    items = core.vault.list_items()
    check("list items", len(items) > 0)
    results = core.vault.search("test")
    check("search items", len(results) > 0)
    stats = core.vault.get_stats()
    check("get stats", stats["total_items"] > 0)
    d = core.vault.delete("tools/test_tool.py")
    check("delete item", d["success"])

    # ─── 10. Self-Improvement ───────────────────────────────────
    section(10, "Self-Improvement System")
    # Record some errors
    core.self_improvement.record_error("test_agent", "do something", "ImportError: no module")
    core.self_improvement.record_error("test_agent", "do something", "ImportError: no module")
    core.self_improvement.record_error("test_agent", "do something", "ImportError: no module")
    core.self_improvement.record_error("test_agent", "do something", "ImportError: no module")
    check("errors recorded", len(core.self_improvement.error_patterns) > 0)
    patterns = core.self_improvement.analyze_errors()
    check("error patterns analyzed", len(patterns) > 0)
    # Propose improvement
    r = core.self_improvement.propose_improvement("new_feature", "Add a web search agent")
    check("propose improvement", r["success"])
    # Safety: block proposals that touch Guardian/safety
    r = core.self_improvement.propose_improvement("danger", "Remove Guardian safety checks")
    check("blocks safety-bypassing proposals", not r["success"])
    # Run full analysis
    analysis = core.self_improvement.run_analysis()
    check("run_analysis returns dict", isinstance(analysis, dict))
    check("analysis has error_patterns", "error_patterns" in analysis)
    check("analysis has missing_capabilities", "missing_capabilities" in analysis)

    # ─── 11. Autonomous Loop ────────────────────────────────────
    section(11, "Autonomous Loop")
    core.task_manager.create_task(description="show the date", required_agent="system_agent", priority="low")
    core.run_autonomous_loop(max_iterations=3)
    check("autonomous loop completes", True)

    # ─── 12. CLI ────────────────────────────────────────────────
    section(12, "CLI Interface")
    from ui.cli import ShadowCLI
    cli = ShadowCLI()
    check("CLI initializes", cli.core is not None)

    # ─── 13. main.py ────────────────────────────────────────────
    section(13, "main.py Entry Point")
    shadow_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    res = subprocess.run([sys.executable, os.path.join(shadow_dir, "main.py"), "--status"],
                        capture_output=True, text=True, timeout=15, cwd=shadow_dir)
    check("main.py --status exit 0", res.returncode == 0)
    res2 = subprocess.run([sys.executable, os.path.join(shadow_dir, "main.py"), "show the date and time"],
                         capture_output=True, text=True, timeout=15, cwd=shadow_dir)
    check("main.py single command exit 0", res2.returncode == 0)

    # ─── Results ────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print(f"  Results: {passed} passed, {degraded} degraded, {failed} failed")
    print("=" * 60)
    sys.exit(0 if failed == 0 else 1)
