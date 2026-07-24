#!/bin/bash
set -eo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "  Shutting down..."

for pidfile in /tmp/stepik_backend.pid /tmp/stepik_frontend.pid; do
  if [ -f "$pidfile" ]; then
    pid=$(cat "$pidfile")
    if kill -0 "$pid" 2>/dev/null; then
      kill -TERM "$pid"
      echo "  Killed PID $pid"
    fi
    rm -f "$pidfile"
  fi
done

docker compose -f "$PROJECT_DIR/docker-compose.yml" down 2>/dev/null || true
echo "  Done."
