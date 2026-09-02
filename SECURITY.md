# Security Policy

## Design principles

- **Sandbox-first execution.** Every command passes through the Guardian
  layer, which audits it, blocks dangerous patterns (recursive deletes,
  forced permission changes, writes to system paths), and logs an audit trail.
- **Checkpoint and rollback.** Guardian takes filesystem checkpoints before
  destructive operations so they can be rolled back.
- **Local-only data.** Memory, tasks, and the vault live in `shadow_data/`
  as local JSON. Nothing leaves the machine unless you run the API server.
- **Token-gated API.** `api_server.py` binds to 127.0.0.1 by default and
  supports bearer-token auth for LAN/remote use.

## Reporting a vulnerability

Please report privately to the repository owner via GitHub's
"Report a vulnerability" feature on the **Security** tab. Include a minimal
reproduction if possible. Please do not open public issues for security bugs.

## Hardening recommendations

- Run `api_server.py` with `--token` on any shared network.
- For remote access, prefer a VPN tunnel (e.g. Tailscale) over open ports.
- Review `guardian/audit.json` entries periodically.
