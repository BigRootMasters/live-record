#!/bin/bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEFAULT_VENV_DIR="$PROJECT_DIR/.venv"
if [ ! -f "$DEFAULT_VENV_DIR/bin/activate" ] && [ -f "$PROJECT_DIR/../.venv/bin/activate" ]; then
  DEFAULT_VENV_DIR="$PROJECT_DIR/../.venv"
fi
VENV_DIR="${VENV_DIR:-$DEFAULT_VENV_DIR}"
LOG_DIR="$PROJECT_DIR/logs"
RUN_DIR="$PROJECT_DIR/run"

mkdir -p "$LOG_DIR" "$RUN_DIR"

if [ ! -f "$VENV_DIR/bin/activate" ]; then
  echo "Virtualenv not found: $VENV_DIR"
  echo "Create it first, for example:"
  echo "  python3.11 -m venv $VENV_DIR"
  exit 1
fi

cd "$PROJECT_DIR"
source "$VENV_DIR/bin/activate"

if [ -f "$RUN_DIR/backend.pid" ] && kill -0 "$(cat "$RUN_DIR/backend.pid")" 2>/dev/null; then
  echo "Backend is already running with PID $(cat "$RUN_DIR/backend.pid")"
else
  echo "Starting backend..."
  nohup gunicorn -c gunicorn.conf.py app:app > "$LOG_DIR/backend.out.log" 2>&1 &
  echo $! > "$RUN_DIR/backend.pid"
fi

for _ in $(seq 1 15); do
  if curl -fsS http://127.0.0.1:5000/health >/dev/null 2>&1; then
    echo "Backend health check passed"
    break
  fi
  sleep 1
done

if ! curl -fsS http://127.0.0.1:5000/health >/dev/null 2>&1; then
  echo "Backend failed to start, see $LOG_DIR/backend.out.log"
  exit 1
fi

if [ -f "$RUN_DIR/scheduler.pid" ] && kill -0 "$(cat "$RUN_DIR/scheduler.pid")" 2>/dev/null; then
  echo "Scheduler is already running with PID $(cat "$RUN_DIR/scheduler.pid")"
else
  echo "Starting scheduler..."
  nohup python run_scheduler.py > "$LOG_DIR/scheduler.out.log" 2>&1 &
  echo $! > "$RUN_DIR/scheduler.pid"
fi

echo "Services started"
echo "Backend log:   $LOG_DIR/backend.out.log"
echo "Scheduler log: $LOG_DIR/scheduler.out.log"
