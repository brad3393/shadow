#!/usr/bin/env bash
# ============================================================
#  ShadowOS installer — turns a minimal Debian install into a
#  dedicated Shadow appliance.
#
#  What it does:
#    1. installs Python + git/curl
#    2. installs Shadow to /opt/shadow (from GitHub)
#    3. creates a dedicated 'shadow' system user
#    4. enables the REST API as a systemd service (0.0.0.0:8787)
#    5. puts Shadow's CLI fullscreen on tty1 — the machine boots
#       straight into Shadow, no login screen
#    6. points Shadow's AI at the desktop PC's Ollama (optional)
#
#  Usage (on a fresh minimal Debian, as root):
#    bash install-shadowos.sh [desktop-tailscale-ip]
#
#  Example:
#    bash install-shadowos.sh 100.84.201.37
# ============================================================
set -euo pipefail

REPO_TARBALL="https://github.com/brad3393/shadow/archive/refs/heads/main.tar.gz"
INSTALL_DIR="/opt/shadow"
SHADOW_USER="shadow"
DESKTOP_IP="${1:-}"
ENV_FILE="/etc/default/shadow"

# --- sanity checks -------------------------------------------
if [ "$(id -u)" -ne 0 ]; then
  echo "[ShadowOS] Run as root:  sudo bash install-shadowos.sh"
  exit 1
fi
if ! command -v apt-get >/dev/null; then
  echo "[ShadowOS] This installer targets Debian/Ubuntu systems (apt-get not found)."
  exit 1
fi

echo "============================================================"
echo "  ShadowOS installer — building your Shadow appliance"
echo "============================================================"

# --- dependencies --------------------------------------------
echo "[1/6] Installing base packages..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq --no-install-recommends python3 git curl ca-certificates >/dev/null

# --- Shadow user ---------------------------------------------
echo "[2/6] Creating system user..."
if ! id "$SHADOW_USER" >/dev/null 2>&1; then
  useradd -r -m -d "/home/$SHADOW_USER" -s /bin/bash "$SHADOW_USER"
fi

# --- fetch Shadow --------------------------------------------
echo "[3/6] Installing Shadow to $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR"
curl -fsSL "$REPO_TARBALL" | tar -xz --strip-components=1 -C "$INSTALL_DIR"
cd "$INSTALL_DIR"
python3 main.py --status >/dev/null
chown -R "$SHADOW_USER":"$SHADOW_USER" "$INSTALL_DIR"
echo "      OK — Shadow verified."

# --- environment ---------------------------------------------
echo "[4/6] Writing configuration..."
mkdir -p /etc/default
cat > "$ENV_FILE" <<EOF
# ShadowOS environment
SHADOW_DATA_DIR=$INSTALL_DIR/shadow_data
SHADOW_API_HOST=0.0.0.0
SHADOW_API_PORT=8787
EOF
if [ -n "$DESKTOP_IP" ]; then
  # Route AI calls to the desktop PC's Ollama over Tailscale
  echo "OLLAMA_HOST=http://$DESKTOP_IP:11434" >> "$ENV_FILE"
  echo "      AI routed to desktop Ollama at $DESKTOP_IP:11434"
else
  echo "      (no desktop IP given — set OLLAMA_HOST in $ENV_FILE later)"
fi
chmod 644 "$ENV_FILE"

# --- systemd services ---------------------------------------
echo "[5/6] Enabling boot services..."

cat > /etc/systemd/system/shadow-api.service <<EOF
[Unit]
Description=Shadow REST API server
After=network-online.target
Wants=network-online.target

[Service]
User=$SHADOW_USER
WorkingDirectory=$INSTALL_DIR
EnvironmentFile=$ENV_FILE
ExecStart=/usr/bin/python3 $INSTALL_DIR/api_server.py --host \$SHADOW_API_HOST --port \$SHADOW_API_PORT
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/shadow-console.service <<EOF
[Unit]
Description=Shadow console (tty1)
After=shadow-api.service
Conflicts=getty@tty1.service
After=getty@tty1.service

[Service]
User=$SHADOW_USER
WorkingDirectory=$INSTALL_DIR
EnvironmentFile=$ENV_FILE
StandardInput=tty
StandardOutput=tty
StandardError=tty
TTYPath=/dev/tty1
TTYReset=yes
TTYVHangup=yes
ExecStart=/usr/bin/python3 $INSTALL_DIR/main.py
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable shadow-api.service >/dev/null 2>&1
systemctl enable shadow-console.service >/dev/null 2>&1
systemctl disable getty@tty1.service >/dev/null 2>&1 || true

# --- console banner ------------------------------------------
cat > /etc/issue <<EOF

  ███████╗██╗  ██╗ ██████╗ ██████╗ ██████╗  ██████╗
  ██╔════╝██║ ██╔╝██╔═══██╗██╔═══██╗██╔══██╗██╔═══██╗
  ███████╗█████╔╝ ██║   ██║██║   ██║██████╔╝██║   ██║
  ╚════██║██╔═██╗ ██║   ██║██║   ██║██╔══██╗██║   ██║
  ███████║██║  ██╗╚██████╔╝╚██████╔╝██║  ██║╚██████╔╝
  ╚══════╝╚═╝  ╚═╝ ╚═════╝  ╚═════╝ ╚═╝  ╚═╝ ╚═════╝
            the machine IS the agent

EOF

echo "[6/6] Done. Reboot to boot straight into Shadow."
echo
echo "  Console: boots fullscreen on the laptop"
echo "  API:     http://<laptop-ip>:8787   (phone access)"
echo "  Config:  $ENV_FILE"
echo
echo "  Reboot now? (y/N)"
read -r REPLY
[ "$REPLY" = "y" ] && reboot || true
