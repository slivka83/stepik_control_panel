#!/bin/bash
set -eo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

check_deps() {
    local missing=()
    for cmd in docker node npm uv; do
        if ! command -v "$cmd" &> /dev/null; then
            missing+=("$cmd")
        fi
    done
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
            exit 1
        fi
    done
    echo "  $name is ready"
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
    rm -f /tmp/stepik_backend.pid /tmp/stepik_frontend.pid
    docker compose -f "$PROJECT_DIR/docker-compose.yml" down 2>/dev/null || true
    echo "  Done."
}

trap cleanup EXIT INT TERM

echo ""
echo "  ┌──────────────────────────────────┐"
echo "  │      Stepik Control Panel         │"
echo "  └──────────────────────────────────┘"
echo ""

echo "[1/3] PostgreSQL + Redis..."
docker compose -f "$PROJECT_DIR/docker-compose.yml" up -d 2>/dev/null
wait_for_service "docker compose -f \"$PROJECT_DIR/docker-compose.yml\" exec -T postgres pg_isready" "PostgreSQL"
wait_for_service "docker compose -f \"$PROJECT_DIR/docker-compose.yml\" exec -T redis redis-cli ping" "Redis"

echo "[2/3] Backend (port $BACKEND_PORT)..."
cd "$PROJECT_DIR/backend"
if [ ! -f ".venv/bin/uvicorn" ]; then
  echo "  Creating Python venv..."
  uv venv --python 3.12 .venv
  echo "  Installing dependencies..."
  uv pip install -r requirements.txt --python .venv
fi
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port "$BACKEND_PORT" --reload --reload-dir app > /tmp/stepik_backend.log 2>&1 &
BACKEND_PID=$!
echo $BACKEND_PID > /tmp/stepik_backend.pid

echo "[3/3] Frontend (port $FRONTEND_PORT)..."
cd "$PROJECT_DIR/frontend"
if [ ! -f "node_modules/.bin/vite" ]; then
  echo "  Installing frontend dependencies..."
  npm install
fi
npx vite --port "$FRONTEND_PORT" > /tmp/stepik_frontend.log 2>&1 &
FRONTEND_PID=$!
echo $FRONTEND_PID > /tmp/stepik_frontend.pid

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
