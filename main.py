#!/usr/bin/env python3
"""Shadow — Main Entry Point

Usage:
  python main.py                    # Start interactive REPL
  python main.py "your command"     # Run a single command
  python main.py --status           # Show system status as JSON
  python main.py --autonomous       # Run autonomous task loop (one cycle)
  python main.py --daemon           # Run as persistent daemon (auto-loop + auto-tasks)
  python main.py --install          # Run install.sh setup
  python main.py --test             # Run the test suite
"""
import sys
import os
import time
import json
import signal
import subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def run_daemon(core, interval=30, max_iterations=10):
    """Run Shadow as a persistent daemon.

    Continuously:
      1. Monitors hardware
      2. Auto-generates maintenance tasks (cleanup, health checks)
      3. Processes the task queue
      4. Runs self-improvement analysis
      5. Writes a heartbeat file so external monitors can check liveness
    """
    from logging.logger import ShadowLogger
    log = ShadowLogger.get("shadow.daemon")

    pid_file = os.path.join(os.path.dirname(__file__), "shadow_data", "shadow.pid")
    os.makedirs(os.path.dirname(pid_file), exist_ok=True)

    # Write PID file
    with open(pid_file, "w") as f:
        f.write(str(os.getpid()))
    log.info(f"Daemon started (PID {os.getpid()})")

    # Graceful shutdown
    def shutdown(signum, frame):
        log.info("Shutdown signal received. Stopping daemon...")
        core.stop()
        if os.path.exists(pid_file):
            os.remove(pid_file)
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    cycle = 0
    while True:
        cycle += 1
        log.info(f"── Daemon cycle {cycle} ──")

        try:
            # 1. Hardware check
            hw = core.hardware.get_status()
            if hw.get("battery_critical") or hw.get("storage_critical"):
                log.warning("Resources critical — pausing daemon for this cycle")
                time.sleep(interval * 2)
                continue

            # 2. Auto-generate maintenance tasks
            _auto_generate_tasks(core)

            # 3. Process task queue
            core.run_autonomous_loop(max_iterations=max_iterations)

            # 4. Self-improvement analysis (every 5 cycles)
            if cycle % 5 == 0:
                analysis = core.self_improvement.run_analysis()
                if analysis.get("error_patterns"):
                    log.info(f"Self-improvement: {len(analysis['error_patterns'])} error patterns detected")
                if analysis.get("missing_capabilities"):
                    for cap in analysis["missing_capabilities"]:
                        log.info(f"Missing capability: {cap}")
                        # Auto-propose creating a new agent
                        core.self_improvement.propose_improvement(
                            "new_agent", f"Create {cap} for autonomous coverage"
                        )

            # 5. Guardian checkpoint cleanup (every 10 cycles)
            if cycle % 10 == 0:
                guardian_script = os.path.join(os.path.dirname(__file__), "guardian", "guardian.sh")
                if os.path.exists(guardian_script):
                    subprocess.run(["bash", guardian_script, "clean", "7"],
                                 capture_output=True, timeout=30)

            # 6. Write heartbeat
            heartbeat = {
                "cycle": cycle,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "pending_tasks": core.task_manager.count_tasks("pending"),
                "completed_tasks": core.task_manager.count_tasks("completed"),
                "agents": list(core.agents.keys()),
                "ollama": core.ollama.is_available() if core.ollama else False,
                "hardware_ok": not hw.get("battery_critical") and not hw.get("storage_critical"),
            }
            hb_path = os.path.join(os.path.dirname(__file__), "shadow_data", "heartbeat.json")
            with open(hb_path, "w") as f:
                json.dump(heartbeat, f, indent=2)

        except Exception as e:
            log.error(f"Daemon cycle {cycle} error: {e}")
            time.sleep(interval)

        # Sleep before next cycle
        log.info(f"Sleeping {interval}s until next cycle...")
        time.sleep(interval)


def _auto_generate_tasks(core):
    """Automatically generate maintenance and health-check tasks."""
    from logging.logger import ShadowLogger
    log = ShadowLogger.get("shadow.daemon")

    # Check what tasks are already pending to avoid duplicates
    pending = core.task_manager.list_tasks()
    pending_descs = [t.get("description", "").lower() for t in pending
                     if t.get("status") == "pending"]

    # Hardware health check
    hw_task = "report current CPU and RAM status"
    if hw_task not in pending_descs:
        core.task_manager.create_task(
            description=hw_task,
            required_agent="hardware_agent",
            priority="low",
        )

    # Security scan (every cycle)
    sec_task = "scan for security issues in this directory"
    if sec_task not in pending_descs:
        core.task_manager.create_task(
            description=sec_task,
            required_agent="security_agent",
            priority="low",
        )

    # System health check
    sys_task = "show system uptime and disk usage"
    if sys_task not in pending_descs:
        core.task_manager.create_task(
            description=sys_task,
            required_agent="system_agent",
            priority="low",
        )

    # If Ollama is available, do a knowledge self-test
    if core.ollama and core.ollama.is_available():
        test_task = "verify that the number 42 is even"
        if test_task not in pending_descs:
            core.task_manager.create_task(
                description=test_task,
                required_agent="testing_agent",
                priority="low",
            )


def main():
    from core.shadow_core import ShadowCore

    # ── --install ───────────────────────────────────────────────
    if "--install" in sys.argv:
        install_script = os.path.join(os.path.dirname(__file__), "install.sh")
        if os.path.exists(install_script):
            os.execvp("bash", ["bash", install_script])
        else:
            print("install.sh not found")
        return

    # ── --test ──────────────────────────────────────────────────
    if "--test" in sys.argv:
        test_script = os.path.join(os.path.dirname(__file__), "tests", "test_shadow.py")
        os.execvp(sys.executable, [sys.executable, test_script])
        return

    # ── --status ────────────────────────────────────────────────
    if "--status" in sys.argv:
        core = ShadowCore()
        core.boot()
        print(json.dumps(core.status(), indent=2))
        return

    # ── --autonomous (one cycle) ────────────────────────────────
    if "--autonomous" in sys.argv:
        core = ShadowCore()
        core.boot()
        print("Starting autonomous loop (single cycle)...")
        core.run_autonomous_loop()
        return

    # ── --daemon (persistent) ───────────────────────────────────
    if "--daemon" in sys.argv:
        core = ShadowCore()
        core.boot()
        interval = 30
        max_iter = 10
        for i, arg in enumerate(sys.argv):
            if arg == "--interval" and i + 1 < len(sys.argv):
                interval = int(sys.argv[i + 1])
            if arg == "--max-iter" and i + 1 < len(sys.argv):
                max_iter = int(sys.argv[i + 1])
        run_daemon(core, interval=interval, max_iterations=max_iter)
        return

    # ── Single command ──────────────────────────────────────────
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        command = " ".join(sys.argv[1:])
        core = ShadowCore()
        core.boot()
        result = core.receive_command(command)
        print(result.get("output", result))
        return

    # ── Interactive REPL ────────────────────────────────────────
    from ui.cli import ShadowCLI
    cli = ShadowCLI()
    cli.run()


if __name__ == "__main__":
    main()
