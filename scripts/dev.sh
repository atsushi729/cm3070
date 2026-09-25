#!/usr/bin/env bash
# One-command local dev orchestrator.
#
# AI inference runs on the host: Ollama uses Apple Metal, while faster-whisper
# uses CTranslate2 on the CPU. Docker Desktop on macOS has no GPU passthrough.
# Only Postgres + Redis run in Docker (see docker-compose.yml). This script wires
# the host processes and the containers together behind a single `make up`.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

RUN_DIR="$ROOT/.dev"
LOG_DIR="$RUN_DIR/logs"
PID_DIR="$RUN_DIR/pids"
mkdir -p "$LOG_DIR" "$PID_DIR"

OLLAMA_HOST_URL="${OLLAMA_HOST:-http://localhost:11434}"
LLM_MODEL_NAME="${LLM_MODEL:-qwen2.5:7b-instruct-q4_K_M}"
VLM_MODEL_NAME="${VLM_MODEL:-qwen2.5vl:7b}"

log()  { printf '\033[1;34m▶ %s\033[0m\n' "$*"; }
ok()   { printf '\033[1;32m✓ %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m! %s\033[0m\n' "$*"; }
die()  { printf '\033[1;31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

tracked_proc_running() {
  local name="$1" pidfile="$PID_DIR/$1.pid"
  [ -f "$pidfile" ] && kill -0 "$(cat "$pidfile")" 2>/dev/null
}

port_is_available() {
  python3 - "$1" <<'PY'
import socket
import sys

with socket.socket() as sock:
    # Allow a quick restart while previous connections are in TIME_WAIT.
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind(("127.0.0.1", int(sys.argv[1])))
    except OSError:
        raise SystemExit(1)
PY
}

ensure_port_available() {
  local name="$1" port="$2"
  tracked_proc_running "$name" && return
  port_is_available "$port" || die \
    "port $port is already in use by another process; stop it, then run: make up"
}

# Start a background host process: name, working dir, command...
start_proc() {
  local name="$1" wd="$2"; shift 2
  local pidfile="$PID_DIR/$name.pid" logfile="$LOG_DIR/$name.log"
  if [ -f "$pidfile" ] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
    ok "$name already running (pid $(cat "$pidfile"))"; return
  fi
  log "starting $name → $logfile"
  ( cd "$wd" && exec "$@" ) >"$logfile" 2>&1 &
  echo $! >"$pidfile"
  ok "$name started (pid $(cat "$pidfile"))"
}

wait_for_proc() {
  local name="$1"
  for _ in 1 2 3 4; do
    sleep 0.25
    tracked_proc_running "$name" || {
      tail -n 30 "$LOG_DIR/$name.log" >&2 2>/dev/null || true
      die "$name exited during startup — see $LOG_DIR/$name.log"
    }
  done
  ok "$name ready"
}

wait_for_http() {
  local name="$1" url="$2"
  log "waiting for ${name}…"
  for _ in $(seq 1 60); do
    if curl -sf "$url" >/dev/null 2>&1; then
      ok "$name ready"
      return
    fi
    tracked_proc_running "$name" || {
      tail -n 30 "$LOG_DIR/$name.log" >&2 2>/dev/null || true
      die "$name exited during startup — see $LOG_DIR/$name.log"
    }
    sleep 1
  done
  tail -n 30 "$LOG_DIR/$name.log" >&2 2>/dev/null || true
  die "$name did not become ready — see $LOG_DIR/$name.log"
}

stop_proc() {
  local name="$1" pidfile="$PID_DIR/$1.pid"
  [ -f "$pidfile" ] || { warn "$name not tracked"; return; }
  local pid; pid="$(cat "$pidfile")"
  if kill -0 "$pid" 2>/dev/null; then
    log "stopping $name (pid $pid)"
    kill "$pid" 2>/dev/null || true
    # give it a moment, then force
    for _ in 1 2 3 4 5; do kill -0 "$pid" 2>/dev/null || break; sleep 0.5; done
    kill -9 "$pid" 2>/dev/null || true
    ok "$name stopped"
  else
    warn "$name was not running"
  fi
  rm -f "$pidfile"
}

ensure_backend() {
  local requirements_hash stamp_file installed_hash
  requirements_hash="$(shasum -a 256 backend/requirements.txt | awk '{print $1}')"
  stamp_file="backend/.venv/.requirements.sha256"
  if [ ! -d backend/.venv ]; then
    log "creating backend virtual environment"
    python3 -m venv backend/.venv
  fi
  installed_hash="$(cat "$stamp_file" 2>/dev/null || true)"
  if [ "$installed_hash" != "$requirements_hash" ]; then
    log "installing backend dependencies"
    backend/.venv/bin/pip install -q --upgrade pip
    backend/.venv/bin/pip install -q -r backend/requirements.txt
    printf '%s\n' "$requirements_hash" >"$stamp_file"
    ok "backend deps installed"
  else
    ok "backend deps already current"
  fi
  if [ ! -f backend/.env ]; then
    cp backend/.env.example backend/.env
    ok "created backend/.env from .env.example"
  fi
}

ensure_frontend() {
  command -v node >/dev/null 2>&1 || die "node not found — install Node.js 22 or newer"
  command -v npm >/dev/null 2>&1 || die "npm not found — install Node.js 22 or newer"
  local node_major lock_hash stamp_file installed_hash
  node_major="$(node -p 'process.versions.node.split(".")[0]')"
  [ "$node_major" -ge 22 ] || die "Node.js 22+ required (found $(node --version))"
  lock_hash="$(shasum -a 256 frontend/package-lock.json | awk '{print $1}')"
  stamp_file="frontend/node_modules/.package-lock.sha256"
  installed_hash="$(cat "$stamp_file" 2>/dev/null || true)"
  if [ ! -d frontend/node_modules ] || [ "$installed_hash" != "$lock_hash" ]; then
    log "installing frontend dependencies"
    ( cd frontend && npm ci --silent )
    printf '%s\n' "$lock_hash" >"$stamp_file"
    ok "frontend deps installed"
  else
    ok "frontend deps already current"
  fi
}

ensure_downloaded_models() {
  log "checking downloadable model assets"
  backend/.venv/bin/python scripts/bootstrap_models.py
}

ensure_ollama_model() {
  local model="$1"
  if ollama list 2>/dev/null | awk 'NR > 1 {print $1}' | grep -Fxq "$model"; then
    ok "Ollama model $model present"
    return
  fi
  log "pulling Ollama model $model (one-time, large download)…"
  ollama pull "$model"
}

ensure_ollama() {
  command -v ollama >/dev/null 2>&1 || die "ollama not found — install it first (macOS: brew install ollama)"
  if ! curl -sf "$OLLAMA_HOST_URL/api/tags" >/dev/null 2>&1; then
    start_proc ollama "$ROOT" ollama serve
    log "waiting for Ollama API…"
    for _ in $(seq 1 30); do
      curl -sf "$OLLAMA_HOST_URL/api/tags" >/dev/null 2>&1 && break; sleep 1
    done
  else
    ok "ollama already serving"
  fi
  ensure_ollama_model "$LLM_MODEL_NAME"
  ensure_ollama_model "$VLM_MODEL_NAME"
}

wait_infra() {
  log "waiting for Postgres + Redis to be healthy…"
  for _ in $(seq 1 60); do
    local db redis
    db="$(docker inspect -f '{{.State.Health.Status}}' sme_db 2>/dev/null || echo none)"
    redis="$(docker inspect -f '{{.State.Health.Status}}' sme_redis 2>/dev/null || echo none)"
    [ "$db" = healthy ] && [ "$redis" = healthy ] && { ok "infrastructure healthy"; return; }
    sleep 1
  done
  die "infrastructure did not become healthy — check: docker compose ps"
}

ensure_docker() {
  command -v docker >/dev/null 2>&1 || die "docker not found — install Docker Desktop"
  # A running Desktop UI does not mean its VM/daemon is healthy. In that state
  # `docker info` can block indefinitely, so bound each readiness probe.
  docker_ready() {
    python3 - <<'PY'
import subprocess

try:
    result = subprocess.run(
        ["docker", "info"], stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, timeout=5,
    )
except subprocess.TimeoutExpired:
    raise SystemExit(1)
raise SystemExit(result.returncode)
PY
  }
  if docker_ready; then ok "Docker daemon running"; return; fi
  if [ "$(uname)" = Darwin ] && [ -d /Applications/Docker.app ]; then
    log "Docker daemon not running — launching Docker Desktop…"
    open -a Docker
    log "waiting up to 2 minutes for Docker daemon (not just the Desktop UI)…"
    for _ in $(seq 1 18); do
      docker_ready && { ok "Docker daemon running"; return; }
      sleep 2
    done
    die "Docker Desktop UI opened, but its daemon is not responding. Restart Docker Desktop, verify 'docker info', then run: make up"
  fi
  die "Docker daemon not responding — start Docker Desktop, verify 'docker info', then run: make up"
}

cmd_up() {
  ensure_port_available backend 8000
  ensure_port_available frontend 3000
  ensure_docker

  log "bringing up infrastructure (Postgres + Redis)"
  docker compose up -d
  wait_infra

  ensure_backend
  ensure_frontend
  ensure_downloaded_models
  ensure_ollama

  local VENV="$ROOT/backend/.venv/bin"
  start_proc backend  "$ROOT/backend"  "$VENV/uvicorn" app.main:app --reload --port 8000
  # Celery has no --reload equivalent, so wrap it in watchmedo: any *.py change
  # under backend/app restarts the worker (SIGTERM = warm shutdown, finishes
  # the in-flight task first). Watch is scoped to app/ so .venv, logs, and
  # uploaded media never trigger a restart.
  start_proc celery   "$ROOT/backend"  "$VENV/watchmedo" auto-restart \
    --directory app --patterns '*.py' --recursive --signal SIGTERM --kill-after 5 \
    -- "$VENV/celery" -A app.celery_app.celery_app worker --loglevel=info --pool=solo --concurrency=1
  start_proc frontend "$ROOT/frontend" npm run dev

  wait_for_proc celery
  wait_for_http backend http://localhost:8000/health
  wait_for_http frontend http://localhost:3000

  echo
  ok "All services up."
  printf '  Frontend : http://localhost:3000\n'
  printf '  API      : http://localhost:8000/health\n'
  printf '  Logs     : make logs   (or tail .dev/logs/*.log)\n'
  printf '  Stop     : make down\n'
}

cmd_down() {
  stop_proc frontend
  stop_proc celery
  stop_proc backend
  stop_proc ollama
  log "stopping containers (volumes preserved)"
  docker compose stop
  ok "All services stopped."
}

cmd_status() {
  printf '\n== Host processes ==\n'
  for name in ollama backend celery frontend; do
    local pidfile="$PID_DIR/$name.pid"
    if [ -f "$pidfile" ] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
      printf '  %-9s running (pid %s)\n' "$name" "$(cat "$pidfile")"
    else
      printf '  %-9s stopped\n' "$name"
    fi
  done
  printf '\n== Containers ==\n'
  docker compose ps 2>/dev/null || true
}

cmd_logs() {
  local files=("$LOG_DIR"/*.log)
  [ -e "${files[0]}" ] || die "no logs yet — run: make up"
  tail -n 40 -F "${files[@]}"
}

case "${1:-up}" in
  up)     cmd_up ;;
  down)   cmd_down ;;
  status) cmd_status ;;
  logs)   cmd_logs ;;
  *)      die "usage: dev.sh {up|down|status|logs}" ;;
esac
