#!/usr/bin/env python3
"""Shadow REST API Server — Mobile/remote interface.

Exposes Shadow's capabilities over HTTP so mobile apps, other machines,
or any client can drive it. Uses only the Python standard library —
fully offline-capable, no dependencies.

Usage:
  python api_server.py                      # Start on port 8787 (localhost only)
  python api_server.py --host 0.0.0.0 --port 8787   # Expose on LAN (for mobile)
  python api_server.py --token mysecret     # Require Bearer token auth

Endpoints:
  GET  /health               → liveness + heartbeat info
  GET  /api/status          → full system status (JSON)
  GET  /api/agents          → registered agents and capabilities
  GET  /api/tasks           → task list
  GET  /api/memory          → memory summary
  POST /api/command         → {"command": "..."} → executes NL command
  POST /api/autonomous      → runs one autonomous loop cycle
  POST /api/tasks           → {"description": "...", "priority": "low"} → create task

Security:
  - Binds to 127.0.0.1 by default. Use --host 0.0.0.0 only on trusted networks.
  - Set --token to require "Authorization: Bearer <token>" on every request.
  - Guardian still audits all commands executed through the API.
"""
import sys
import os
import json
import argparse
from http.server import HTTPServer, BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from logging.logger import ShadowLogger

log = ShadowLogger.get("shadow.api")


class ShadowAPIHandler(BaseHTTPRequestHandler):
    core = None
    api_token = None

    def _auth_ok(self):
        if not self.api_token:
            return True
        header = self.headers.get("Authorization", "")
        return header == f"Bearer {self.api_token}"

    def _send_json(self, data, status=200):
        body = json.dumps(data, indent=2, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode())
        except json.JSONDecodeError:
            return None

    def log_message(self, fmt, *args):
        log.info(f"{self.client_address[0]} {fmt % args}")

    # ── GET ─────────────────────────────────────────────────
    def do_GET(self):
        if not self._auth_ok():
            return self._send_json({"error": "unauthorized"}, 401)

        path = self.path.split("?")[0]
        try:
            if path == "/health":
                hb_path = os.path.join(os.path.dirname(__file__), "shadow_data", "heartbeat.json")
                heartbeat = None
                if os.path.exists(hb_path):
                    with open(hb_path) as f:
                        heartbeat = json.load(f)
                return self._send_json({"status": "online", "heartbeat": heartbeat})

            if path == "/api/status":
                return self._send_json(self.core.status())

            if path == "/api/agents":
                agents = {}
                for name, agent in self.core.agents.items():
                    agents[name] = {
                        "description": getattr(agent, "description", ""),
                        "keywords": getattr(agent, "keywords", []),
                    }
                return self._send_json({"agents": agents})

            if path == "/api/tasks":
                return self._send_json({"tasks": self.core.task_manager.list_tasks()})

            if path == "/api/memory":
                return self._send_json(self.core.memory.summary() if hasattr(self.core.memory, "summary")
                                       else {"categories": self.core.memory.categories
                                             if hasattr(self.core.memory, "categories") else {}})

            return self._send_json({"error": f"unknown endpoint {path}"}, 404)
        except Exception as e:
            log.error(f"GET {path} failed: {e}")
            return self._send_json({"error": str(e)}, 500)

    # ── POST ────────────────────────────────────────────────
    def do_POST(self):
        if not self._auth_ok():
            return self._send_json({"error": "unauthorized"}, 401)

        path = self.path.split("?")[0]
        body = self._read_body()
        if body is None:
            return self._send_json({"error": "invalid JSON"}, 400)

        try:
            if path == "/api/command":
                command = body.get("command", "").strip()
                if not command:
                    return self._send_json({"error": "missing 'command'"}, 400)
                log.info(f"API command: {command[:100]}")
                result = self.core.receive_command(command)
                return self._send_json(result)

            if path == "/api/autonomous":
                self.core.run_autonomous_loop()
                return self._send_json({"status": "autonomous cycle complete"})

            if path == "/api/tasks":
                desc = body.get("description", "").strip()
                if not desc:
                    return self._send_json({"error": "missing 'description'"}, 400)
                task = self.core.task_manager.create_task(
                    description=desc,
                    required_agent=body.get("required_agent"),
                    priority=body.get("priority", "medium"),
                )
                return self._send_json({"status": "created", "task": task})

            return self._send_json({"error": f"unknown endpoint {path}"}, 404)
        except Exception as e:
            log.error(f"POST {path} failed: {e}")
            return self._send_json({"error": str(e)}, 500)


def main():
    parser = argparse.ArgumentParser(description="Shadow REST API Server")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (use 0.0.0.0 for LAN)")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--token", default=os.environ.get("SHADOW_API_TOKEN", ""),
                        help="Require Bearer token auth")
    args = parser.parse_args()

    from core.shadow_core import ShadowCore
    core = ShadowCore()
    core.boot()

    ShadowAPIHandler.core = core
    ShadowAPIHandler.api_token = args.token or None

    server = HTTPServer((args.host, args.port), ShadowAPIHandler)
    log.info(f"Shadow API listening on http://{args.host}:{args.port}")
    log.info(f"Auth: {'token required' if ShadowAPIHandler.api_token else 'open (localhost only recommended)'}")
    print(f"Shadow API: http://{args.host}:{args.port}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("API server shutting down.")
        server.server_close()
        core.stop()


if __name__ == "__main__":
    main()
