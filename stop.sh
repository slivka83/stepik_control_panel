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

if [ -f "$PROJECT_DIR/.env" ]; then
    BACKEND_PORT=$(grep -E "^BACKEND_PORT=" "$PROJECT_DIR/.env" | cut -d= -f2 | tr -d ' ' || true)
    FRONTEND_PORT=$(grep -E "^FRONTEND_PORT=" "$PROJECT_DIR/.env" | cut -d= -f2 | tr -d ' ' || true)
    PG_USER=$(grep -E "^POSTGRES_USER=" "$PROJECT_DIR/.env" | cut -d= -f2 | tr -d ' ' || true)
    PG_DB=$(grep -E "^POSTGRES_DB=" "$PROJECT_DIR/.env" | cut -d= -f2 | tr -d ' ' || true)
fi
BACKEND_PORT=${BACKEND_PORT:-8000}
FRONTEND_PORT=${FRONTEND_PORT:-3000}
PG_USER=${PG_USER:-stepik_panel}
PG_DB=${PG_DB:-stepik_panel}

# Vite and uvicorn spawn child processes; killing only the parent leaves them
# holding the port. Sweep listeners on our ports, but only processes started
# from this project — a foreign server on 8000/3000 must not be killed.
is_our_process() {
    local pid="$1"
    local cwd=""
    cwd=$(readlink "/proc/$pid/cwd" 2>/dev/null || true)
    if [ -n "$cwd" ]; then
        case "$cwd" in
            "$PROJECT_DIR"*) ;;
            *) return 1 ;;
        esac
        tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null \
            | grep -Eq 'uvicorn|app\.main:app|vite|node|npm'
        return
    fi
    # macOS has no /proc: fall back to the command line (best effort).
    ps -p "$pid" -o command= 2>/dev/null \
        | grep -Eq 'uvicorn|app\.main:app|vite|node|npm'
}

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
        if ! is_our_process "$pid"; then
            echo "  Port $port is held by another process (PID $pid) — left untouched"
            continue
        fi
        if kill -TERM "$pid" 2>/dev/null; then
            echo "  Freed port $port (PID $pid)"
        fi
    done
}

# --- Бэкап (как stop.bat: данные важнее скорости остановки) ---------------
BACKUP_DIR="$PROJECT_DIR/backups"
mkdir -p "$BACKUP_DIR"
STAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/stepik_${STAMP}_stop.dump"
if "${COMPOSE[@]}" -f "$PROJECT_DIR/docker-compose.yml" exec -T postgres \
        pg_dump -U "$PG_USER" -d "$PG_DB" -Fc > "$BACKUP_FILE" 2>/dev/null; then
    if [ -s "$BACKUP_FILE" ]; then
        echo "  Backup saved: $(basename "$BACKUP_FILE")"
        ls -1t "$BACKUP_DIR"/stepik_*.dump 2>/dev/null | tail -n +11 | while IFS= read -r old; do
            rm -f "$old"
        done
    else
        rm -f "$BACKUP_FILE"
        echo "  Backup skipped: pg_dump produced an empty file"
    fi
else
    rm -f "$BACKUP_FILE"
    echo "  Backup skipped: database container is not running"
fi

echo "  Shutting down..."

for pidfile in /tmp/stepik_backend.pid /tmp/stepik_frontend.pid; do
  if [ -f "$pidfile" ]; then
    pid=$(cat "$pidfile")
    # PID files can survive a reboot; never kill a reused PID from another app.
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null && is_our_process "$pid"; then
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
