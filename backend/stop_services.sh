#!/bin/bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
RUN_DIR="$PROJECT_DIR/run"

stop_pid_file() {
  local pid_file="$1"
  local name="$2"

  if [ ! -f "$pid_file" ]; then
    echo "$name is not running"
    return
  fi

  local pid
  pid="$(cat "$pid_file")"
  if kill -0 "$pid" 2>/dev/null; then
    echo "Stopping $name ($pid)..."
    kill "$pid"
  else
    echo "$name pid file exists but process is gone"
  fi

  rm -f "$pid_file"
}

stop_pid_file "$RUN_DIR/scheduler.pid" "scheduler"
stop_pid_file "$RUN_DIR/backend.pid" "backend"
