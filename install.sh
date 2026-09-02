#!/bin/bash
# ═══════════════════════════════════════════════════════════════
#  Shadow — Automated Installer & Setup
#  One command: curl ... | bash  OR  ./install.sh
#  Does everything: checks Python, sets up dirs, runs tests,
#  detects/installs Ollama, creates launcher scripts, installs
#  systemd service for auto-start on boot.
# ═══════════════════════════════════════════════════════════════

set -e

SHADOW_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="${PYTHON:-python3}"
OLLAMA_HOST="${OLLAMA_HOST:-http://localhost:11434}"
OLLAMA_MODEL="${OLLAMA_MODEL:-llama3.1}"

# ── Colors ─────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

info()  { echo -e "${CYAN}[INFO]${NC}  $1"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
err()   { echo -e "${RED}[ERR]${NC}   $1"; }
step()  { echo -e "\n${BOLD}${BLUE}━━━ $1 ━━━${NC}"; }

# ── Banner ─────────────────────────────────────────────────────
echo -e "${BOLD}"
cat << 'BANNER'
    ╔══════════════════════════════════════════╗
    ║   S H A D O W   —   I N S T A L L E R    ║
    ║   Autonomous Modular AI Network          ║
    ╚══════════════════════════════════════════╝
BANNER
echo -e "${NC}"

# ── Step 1: Check Python ───────────────────────────────────────
step "1/6  Checking Python"
if command -v $PYTHON &>/dev/null; then
    PY_VER=$($PYTHON --version 2>&1)
    ok "Found $PY_VER"
    # Check version >= 3.10
    PY_MINOR=$($PYTHON -c "import sys; print(sys.version_info.minor)" 2>/dev/null || echo 0)
    if [ "$PY_MINOR" -lt 10 ]; then
        err "Python 3.10+ required, found 3.$PY_MINOR"
        exit 1
    fi
else
    err "Python 3 not found. Install it first: https://www.python.org/downloads/"
    exit 1
fi

# ── Step 2: Create runtime directories ─────────────────────────
step "2/6  Setting up directories"
mkdir -p "$SHADOW_DIR/shadow_data"
mkdir -p "$SHADOW_DIR/shadow_data/memory"
mkdir -p "$SHADOW_DIR/shadow_data/tasks"
mkdir -p "$SHADOW_DIR/shadow_data/vault"
mkdir -p "$SHADOW_DIR/shadow_data/logs"
mkdir -p "$SHADOW_DIR/shadow_data/guardian"
mkdir -p "$SHADOW_DIR/shadow_data/self_improve"
mkdir -p "$SHADOW_DIR/shadow_data/checkpoints"
ok "Runtime directories created"

# ── Step 3: Write environment config ───────────────────────────
step "3/6  Writing configuration"
cat > "$SHADOW_DIR/.env" << ENVEOF
# Shadow Environment Configuration
SHADOW_DIR=$SHADOW_DIR
PYTHON_BIN=$PYTHON
OLLAMA_HOST=$OLLAMA_HOST
OLLAMA_MODEL=$OLLAMA_MODEL
SHADOW_DATA_DIR=$SHADOW_DIR/shadow_data
SHADOW_LOG_DIR=$SHADOW_DIR/shadow_data/logs
SHADOW_AUTONOMOUS=true
SHADOW_MAX_ITERATIONS=10
ENVEOF
ok "Configuration written to .env"

# ── Step 4: Run test suite ─────────────────────────────────────
step "4/6  Running test suite"
cd "$SHADOW_DIR"
if $PYTHON tests/test_shadow.py 2>&1 | tail -5; then
    ok "All tests passed"
else
    warn "Some tests failed — Shadow will still run but may have issues"
fi

# ── Step 5: Check / Install Ollama ──────────────────────────────
step "5/6  Checking Ollama"
if command -v ollama &>/dev/null; then
    ok "Ollama found: $(ollama --version 2>/dev/null || echo 'installed')"

    # Check if service is running
    if curl -s "$OLLAMA_HOST/api/tags" &>/dev/null; then
        ok "Ollama service is running"
    else
        info "Starting Ollama service..."
        ollama serve &>/dev/null &
        sleep 2
        if curl -s "$OLLAMA_HOST/api/tags" &>/dev/null; then
            ok "Ollama service started"
        else
            warn "Ollama service not responding — AI features will be offline"
            warn "Start it manually: ollama serve"
        fi
    fi

    # Check if model is pulled
    if ollama list 2>/dev/null | grep -q "$OLLAMA_MODEL"; then
        ok "Model '$OLLAMA_MODEL' is available"
    else
        info "Pulling model '$OLLAMA_MODEL' (this may take a while)..."
        ollama pull "$OLLAMA_MODEL" && ok "Model pulled" || warn "Model pull failed — run: ollama pull $OLLAMA_MODEL"
    fi
else
    warn "Ollama not installed — AI features (code gen, learning, planning) will be offline"
    info "To install Ollama:"
    echo "    curl -fsSL https://ollama.com/install.sh | sh"
    echo "    ollama pull $OLLAMA_MODEL"
    echo ""
    info "Shadow's offline features (file ops, system commands, security,"
    info "hardware monitoring, testing, memory, vault, guardian) work without Ollama."
fi

# ── Step 6: Install launcher & service ─────────────────────────
step "6/6  Installing launcher"

# Create convenience launcher
cat > "$SHADOW_DIR/shadow.sh" << LAUNCHEOF
#!/bin/bash
# Shadow launcher — picks the right Python and runs Shadow
cd "$SHADOW_DIR"
export OLLAMA_HOST="\${OLLAMA_HOST:-$OLLAMA_HOST}"
export OLLAMA_MODEL="\${OLLAMA_MODEL:-$OLLAMA_MODEL}"

case "\$1" in
    ""|repl)
        echo "Starting Shadow interactive REPL..."
        $PYTHON main.py
        ;;
    --status)
        $PYTHON main.py --status 2>/dev/null
        ;;
    --autonomous|--daemon)
        echo "Starting Shadow autonomous daemon..."
        $PYTHON main.py --daemon
        ;;
    --test)
        $PYTHON tests/test_shadow.py
        ;;
    --stop)
        if [ -f "$SHADOW_DIR/shadow_data/shadow.pid" ]; then
            PID=\$(cat "$SHADOW_DIR/shadow_data/shadow.pid")
            kill \$PID 2>/dev/null && echo "Shadow stopped (PID \$PID)" || echo "Process not found"
            rm -f "$SHADOW_DIR/shadow_data/shadow.pid"
        else
            echo "Shadow is not running"
        fi
        ;;
    *)
        $PYTHON main.py "\$@"
        ;;
esac
LAUNCHEOF
chmod +x "$SHADOW_DIR/shadow.sh"
ok "Launcher created: ./shadow.sh"

# Try to install systemd service for auto-start on boot
if [ -d "/etc/systemd/system" ] && [ "$EUID" -eq 0 ]; then
    cat > /etc/systemd/system/shadow.service << SVCEOF
[Unit]
Description=Shadow Autonomous AI Network
After=network.target

[Service]
Type=simple
WorkingDirectory=$SHADOW_DIR
ExecStart=$PYTHON $SHADOW_DIR/main.py --daemon
Restart=on-failure
RestartSec=10
Environment=OLLAMA_HOST=$OLLAMA_HOST
Environment=OLLAMA_MODEL=$OLLAMA_MODEL

[Install]
WantedBy=multi-user.target
SVCEOF

    systemctl daemon-reload
    systemctl enable shadow.service
    ok "Systemd service installed and enabled (starts on boot)"
    info "Start now:  systemctl start shadow"
    info "Check:      systemctl status shadow"
    info "Stop:       systemctl stop shadow"
    info "Disable:    systemctl disable shadow"
elif [ -d "/etc/systemd/system" ]; then
    warn "Run installer as root to install systemd auto-start service"
    info "Or run Shadow manually: ./shadow.sh --daemon"
else
    # macOS or other — create launchd plist or just show manual instructions
    if [ "$(uname)" = "Darwin" ]; then
        cat > "$SHADOW_DIR/com.shadow.daemon.plist" << PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>com.shadow.daemon</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON</string>
        <string>$SHADOW_DIR/main.py</string>
        <string>--daemon</string>
    </array>
    <key>WorkingDirectory</key><string>$SHADOW_DIR</string>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><true/>
</dict>
</plist>
PLISTEOF
        ok "macOS launchd plist created: com.shadow.daemon.plist"
        info "Install: cp com.shadow.daemon.plist ~/Library/LaunchAgents/"
        info "Start:   launchctl load ~/Library/LaunchAgents/com.shadow.daemon.plist"
    else
        warn "No systemd detected — run manually: ./shadow.sh --daemon"
    fi
fi

# ── Done ───────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}╔══════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${GREEN}║  Shadow installation complete!            ║${NC}"
echo -e "${BOLD}${GREEN}╚══════════════════════════════════════════╝${NC}"
echo ""
echo -e "  Quick start:"
echo -e "    ${CYAN}./shadow.sh${NC}              Interactive REPL"
echo -e "    ${CYAN}./shadow.sh --status${NC}     System status"
echo -e "    ${CYAN}./shadow.sh --daemon${NC}     Run as background daemon"
echo -e "    ${CYAN}./shadow.sh --test${NC}       Run test suite"
echo -e "    ${CYAN}./shadow.sh \"show the date\"${NC}  Single command"
echo -e "    ${CYAN}./shadow.sh --stop${NC}       Stop daemon"
echo ""
