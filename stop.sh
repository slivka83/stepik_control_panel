#!/bin/bash
set -eo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Same engine as start.sh: podman by default, docker via CONTAINER_ENGINE=docker
export PATH="$HOME/.local/bin:$PATH"
CONTAINER_ENGINE="${CONTAINER_ENGINE:-podman}"
case "$CONTAINER_ENGINE" in
    podman) COMPOSE=(podman-compose) ;;
    docker) COMPOSE=(docker compose) ;;
    *)
        echo "Unknown CONTAINER_ENGINE: $CONTAINER_ENGINE (expected: podman or docker)"
        exit 1
        ;;
esac

BACKEND_PORT=$(grep -E "^BACKEND_PORT=" "$PROJECT_DIR/.env" | cut -d= -f2 | tr -d ' ')
FRONTEND_PORT=$(grep -E "^FRONTEND_PORT=" "$PROJECT_DIR/.env" | cut -d= -f2 | tr -d ' ')
BACKEND_PORT=${BACKEND_PORT:-8000}
FRONTEND_PORT=${FRONTEND_PORT:-3000}

# Vite and uvicorn spawn child processes; killing only the parent leaves them
# holding the port. Sweep every listener on our ports instead.
free_port() {
    local port="$1"
    local pids
    pids=$(ss -ltnp 2>/dev/null \
        | grep -E "[:.]${port}[[:space:]]" \
        | grep -oE 'pid=[0-9]+' \
        | cut -d= -f2 \
        | sort -u) || true
    for pid in $pids; do
        [ "$pid" = "$$" ] && continue
        if kill -TERM "$pid" 2>/dev/null; then
            echo "  Freed port $port (PID $pid)"
        fi
    done
}

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

free_port "$BACKEND_PORT"
free_port "$FRONTEND_PORT"

"${COMPOSE[@]}" -f "$PROJECT_DIR/docker-compose.yml" down 2>/dev/null || true
echo "  Done."
