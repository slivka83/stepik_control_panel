#!/bin/bash
set -eo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

# podman-compose lives in ~/.local/bin, which is not always on PATH (non-login shells)
export PATH="$HOME/.local/bin:$PATH"

# Container engine for PostgreSQL + Redis: podman (default, no Docker Desktop needed)
# or docker. Override: CONTAINER_ENGINE=docker ./start.sh
CONTAINER_ENGINE="${CONTAINER_ENGINE:-podman}"
case "$CONTAINER_ENGINE" in
    podman) COMPOSE=(podman-compose) ;;
    docker) COMPOSE=(docker compose) ;;
    *)
        echo "Unknown CONTAINER_ENGINE: $CONTAINER_ENGINE (expected: podman or docker)"
        exit 1
        ;;
esac

check_deps() {
    local missing=()
    for cmd in node npm uv; do
        if ! command -v "$cmd" &> /dev/null; then
            missing+=("$cmd")
        fi
    done
    if [ "$CONTAINER_ENGINE" = "podman" ]; then
        command -v podman &> /dev/null || missing+=("podman")
        command -v podman-compose &> /dev/null || missing+=("podman-compose")
    else
        command -v docker &> /dev/null || missing+=("docker")
    fi
    if [ ${#missing[@]} -gt 0 ]; then
        echo "Missing dependencies: ${missing[*]}"
        echo "Please install them and try again."
        exit 1
    fi
}

DETACH=0
for arg in "$@"; do
  case "$arg" in
    -d|--detach) DETACH=1 ;;
  esac
done

check_deps

if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo ".env file not found. Copy from .env.example and fill in values."
    exit 1
fi

BACKEND_PORT=$(grep -E "^BACKEND_PORT=" "$PROJECT_DIR/.env" | cut -d= -f2 | tr -d ' ')
FRONTEND_PORT=$(grep -E "^FRONTEND_PORT=" "$PROJECT_DIR/.env" | cut -d= -f2 | tr -d ' ')
BACKEND_PORT=${BACKEND_PORT:-8000}
FRONTEND_PORT=${FRONTEND_PORT:-3000}

wait_for_service() {
    local cmd="$1"
    local name="$2"
    local timeout=30
    local elapsed=0
    while ! eval "$cmd" > /dev/null 2>&1; do
        sleep 1
        elapsed=$((elapsed + 1))
        if [ $elapsed -ge $timeout ]; then
            echo "Timeout waiting for $name"
            local other="podman"
            [ "$CONTAINER_ENGINE" = "podman" ] && other="docker"
            echo "If it is already running under $other, stop that first:"
            echo "  CONTAINER_ENGINE=$other ./stop.sh"
            exit 1
        fi
    done
    echo "  $name is ready"
}

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
        kill -TERM "$pid" 2>/dev/null
    done
}

# Detached launch: the process gets its own session (setsid), so it survives the
# death of the parent session - e.g. start.bat -> wsl.exe -> cmd.exe on Windows.
launch_bg() {
    local pidfile="$1"
    local logfile="$2"
    shift 2
    if [ "$DETACH" -eq 1 ]; then
        setsid bash -c 'pidfile="$1"; logfile="$2"; shift 2; printf "%s" "$$" > "$pidfile"; exec "$@" > "$logfile" 2>&1 < /dev/null' \
            _ "$pidfile" "$logfile" "$@" &
        for _ in $(seq 1 30); do
            [ -s "$pidfile" ] && break
            sleep 0.1
        done
    else
        "$@" > "$logfile" 2>&1 &
        printf "%s" "$!" > "$pidfile"
    fi
}

CLEANED=0
BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
    [ "$CLEANED" -eq 1 ] && return
    CLEANED=1
    echo ""
    echo "  Shutting down..."
    [ -n "$BACKEND_PID" ] && kill -TERM "$BACKEND_PID" 2>/dev/null
    [ -n "$FRONTEND_PID" ] && kill -TERM "$FRONTEND_PID" 2>/dev/null
    for i in $(seq 1 10); do
        BACKEND_ALIVE=0
        FRONTEND_ALIVE=0
        kill -0 "$BACKEND_PID" 2>/dev/null && BACKEND_ALIVE=1
        kill -0 "$FRONTEND_PID" 2>/dev/null && FRONTEND_ALIVE=1
        if [ "$BACKEND_ALIVE" -eq 0 ] && [ "$FRONTEND_ALIVE" -eq 0 ]; then
            break
        fi
        sleep 1
    done
    [ -n "$BACKEND_PID" ] && kill -9 "$BACKEND_PID" 2>/dev/null
    [ -n "$FRONTEND_PID" ] && kill -9 "$FRONTEND_PID" 2>/dev/null
    # vite/uvicorn spawn child processes that outlive their parent and keep the port
    free_port "$BACKEND_PORT"
    free_port "$FRONTEND_PORT"
    rm -f /tmp/stepik_backend.pid /tmp/stepik_frontend.pid
    "${COMPOSE[@]}" -f "$PROJECT_DIR/docker-compose.yml" down 2>/dev/null || true
    echo "  Done."
}

trap cleanup EXIT INT TERM

echo ""
echo "  ┌──────────────────────────────────┐"
echo "  │      Stepik Control Panel         │"
echo "  └──────────────────────────────────┘"
echo ""

echo "[1/3] PostgreSQL + Redis ($CONTAINER_ENGINE)..."
"${COMPOSE[@]}" -f "$PROJECT_DIR/docker-compose.yml" up -d 2>/dev/null
wait_for_service "\"${COMPOSE[*]}\" -f \"$PROJECT_DIR/docker-compose.yml\" exec -T postgres pg_isready" "PostgreSQL"
wait_for_service "\"${COMPOSE[*]}\" -f \"$PROJECT_DIR/docker-compose.yml\" exec -T redis redis-cli ping" "Redis"

echo "[2/3] Backend (port $BACKEND_PORT)..."
cd "$PROJECT_DIR/backend"
if [ ! -f ".venv/bin/uvicorn" ]; then
  echo "  Creating Python venv..."
  uv venv --clear --python 3.12 .venv
  echo "  Installing dependencies..."
  uv pip install -r requirements.txt --python .venv
fi
launch_bg /tmp/stepik_backend.pid /tmp/stepik_backend.log \
    .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port "$BACKEND_PORT" --reload --reload-dir app
BACKEND_PID=$(cat /tmp/stepik_backend.pid 2>/dev/null || true)

echo "[3/3] Frontend (port $FRONTEND_PORT)..."
cd "$PROJECT_DIR/frontend"
if [ ! -f "node_modules/.bin/vite" ]; then
    echo "  Installing frontend dependencies..."
    npm install
fi
launch_bg /tmp/stepik_frontend.pid /tmp/stepik_frontend.log \
    npx vite --port "$FRONTEND_PORT"
FRONTEND_PID=$(cat /tmp/stepik_frontend.pid 2>/dev/null || true)

echo ""
echo "  ┌──────────────────────────────────┐"
echo "  │  Open in browser:                 │"
echo "  │                                  │"
echo "  │  → http://localhost:$FRONTEND_PORT"
echo "  │                                  │"
echo "  │  API: http://localhost:$BACKEND_PORT"
echo "  └──────────────────────────────────┘"
echo ""
if [ "$DETACH" -eq 1 ]; then
  trap - EXIT INT TERM
  echo "  Backend PID:  $(cat /tmp/stepik_backend.pid)"
  echo "  Frontend PID: $(cat /tmp/stepik_frontend.pid)"
  echo "  Logs: /tmp/stepik_backend.log, /tmp/stepik_frontend.log"
  echo ""
  echo "  Stop: ./stop.sh"
  echo ""
  exit 0
fi

echo "  Stop: Ctrl+C"
echo ""

wait "$BACKEND_PID" 2>/dev/null
wait "$FRONTEND_PID" 2>/dev/null
