#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
#  ShadowOS Android installer — installs Shadow as a resident
#  node on any Android phone (Pixel 7 tested target).
#
#  Runs INSIDE Termux. Shadow installs to ~/shadow with his CLI
#  and a localhost-only REST API. Nothing is ever exposed to
#  mobile/hotel networks.
#
#  Usage:
#    pkg install curl -y
#    curl -fsSL https://raw.githubusercontent.com/brad3393/shadow/main/shadowos/install-shadow-android.sh | bash
# ============================================================
set -euo pipefail

REPO_TARBALL="https://github.com/brad3393/shadow/archive/refs/heads/main.tar.gz"
INSTALL_DIR="$HOME/shadow"

# --- sanity: must be Termux ----------------------------------
if [ -z "${TERMUX_VERSION:-}" ]; then
  echo "[Shadow] This installer must run inside Termux (F-Droid version)."
  exit 1
fi

echo "============================================================"
echo "  ShadowOS — Android node install"
echo "============================================================"

echo "[1/4] Installing Python..."
yes | pkg update >/dev/null 2>&1 || true
yes | pkg install python curl >/dev/null 2>&1 || pkg install -y python curl

echo "[2/4] Installing Shadow to $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR"
curl -fsSL "$REPO_TARBALL" | tar -xz --strip-components=1 -C "$INSTALL_DIR"
cd "$INSTALL_DIR"

echo "[3/4] Verifying..."
python main.py --status
echo "      OK — Shadow verified on this phone."

echo "[4/4] Creating launcher..."
cat > "$HOME/shadow-start.sh" <<'EOF'
#!/data/data/com.termux/files/usr/bin/bash
# Starts Shadow: API on localhost only + drops into his CLI.
cd "$HOME/shadow"
# API stays on 127.0.0.1 — NEVER exposed to mobile/hotel networks.
(python api_server.py --host 127.0.0.1 --port 8787 >/dev/null 2>&1 &)
echo "Shadow API on http://127.0.0.1:8787 (this phone only)"
python main.py
EOF
chmod +x "$HOME/shadow-start.sh"

# Optional: auto-start at phone boot if Termux:Boot is installed
BOOT_DIR="$HOME/.termux/boot"
if [ -d "$BOOT_DIR" ]; then
  cp "$HOME/shadow-start.sh" "$BOOT_DIR/shadow-boot.sh"
  echo "      Termux:Boot detected — Shadow starts at phone boot."
else
  echo "      (Optional: install the Termux:Boot add-on for start-at-boot)"
fi

echo
echo "Done. Shadow lives on this phone now."
echo
echo "  Start him:    bash ~/shadow-start.sh"
echo "  His API:      http://127.0.0.1:8787  (local only, always)"
echo "  His brain:    ~/shadow/shadow_data"
echo
echo "  Note: AI runs in stub/template mode on the phone (same as the"
echo "  laptop) — orchestration, memory and all 10 agents are fully live."
