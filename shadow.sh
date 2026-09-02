#!/usr/bin/env bash
# Shadow launcher — thin wrapper around main.py
set -e
cd "$(dirname "$0")"

case "${1:-}" in
  --help|-h)
    echo "Shadow — autonomous AI network"
    echo ""
    echo "Usage:"
    echo "  ./shadow.sh                  Start interactive REPL"
    echo "  ./shadow.sh \"<command>\"     Run a single command"
    echo "  ./shadow.sh --status         JSON system status"
    echo "  ./shadow.sh --autonomous     Run one autonomous cycle"
    echo "  ./shadow.sh --daemon          Persistent daemon mode"
    echo "  ./shadow.sh --api             Start REST API (port 8787)"
    echo "  ./shadow.sh --test           Run the test suite"
    echo "  ./shadow.sh --install         Run install.sh setup"
    ;;
  --api)
    shift
    exec python3 api_server.py "$@"
    ;;
  *)
    exec python3 main.py "$@"
    ;;
esac
