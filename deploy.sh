#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
VENV_DIR="$BACKEND_DIR/.venv"
PYTHON_BIN="${PYTHON_BIN:-python3.11}"
PIP_INDEX_URL="${DEPLOY_PIP_INDEX_URL:-https://mirrors.aliyun.com/pypi/simple/}"
RPM_FUSION_URL="${DEPLOY_RPM_FUSION_URL:-https://mirrors.aliyun.com/rpmfusion/free/el/rpmfusion-free-release-8.noarch.rpm}"
EPEL_RELEASE_URL="${DEPLOY_EPEL_RELEASE_URL:-https://mirrors.aliyun.com/epel/epel-release-latest-8.noarch.rpm}"

PULL_CODE=1
INSTALL_SYSTEM_DEPS=1
RUN_TESTS=1
UNIT_TMP_DIR=""

log() {
  echo "[deploy] $*"
}

die() {
  echo "[deploy] ERROR: $*" >&2
  exit 1
}

usage() {
  cat <<'EOF'
Usage: ./deploy.sh [options]

Idempotent deployment for Alibaba Cloud Linux 3:
  - pulls origin/main with fast-forward only
  - installs Python 3.11, pip, ffmpeg and ffprobe when missing
  - creates backend/.venv and installs Python requirements
  - validates configuration and runs tests
  - installs systemd units for the current repository path
  - restarts the API and scheduler, then checks health

Options:
  --skip-pull          Do not run git pull (useful while testing local changes)
  --skip-system-deps   Do not install OS packages
  --skip-tests         Do not run the unittest suite
  -h, --help           Show this help

Environment overrides:
  PYTHON_BIN                 Python executable, default: python3.11
  DEPLOY_PIP_INDEX_URL       pip index URL
  DEPLOY_RPM_FUSION_URL      RPM Fusion EL8 release RPM URL
  DEPLOY_EPEL_RELEASE_URL    EPEL 8 release RPM URL
EOF
}

cleanup() {
  if [[ -n "$UNIT_TMP_DIR" && -d "$UNIT_TMP_DIR" ]]; then
    rm -rf -- "$UNIT_TMP_DIR"
  fi
}
trap cleanup EXIT

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-pull)
      PULL_CODE=0
      ;;
    --skip-system-deps)
      INSTALL_SYSTEM_DEPS=0
      ;;
    --skip-tests)
      RUN_TESTS=0
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage >&2
      die "Unknown option: $1"
      ;;
  esac
  shift
done

[[ "${EUID:-$(id -u)}" -eq 0 ]] || die "Run this script as root"
[[ -d "$PROJECT_ROOT/.git" ]] || die "Git repository not found: $PROJECT_ROOT"
[[ -f "$BACKEND_DIR/requirements.txt" ]] || die "requirements.txt not found"
[[ -f "$BACKEND_DIR/.env" ]] || die "backend/.env not found"
[[ -f "$BACKEND_DIR/config/anchors.json" ]] || die "anchors.json not found"

if [[ "$PROJECT_ROOT" =~ [[:space:]\&] ]]; then
  die "Repository path must not contain whitespace or &: $PROJECT_ROOT"
fi

pull_code() {
  if [[ "$PULL_CODE" -ne 1 ]]; then
    log "Skipping git pull"
    return
  fi

  if [[ -n "$(git -C "$PROJECT_ROOT" status --porcelain --untracked-files=no)" ]]; then
    die "Tracked files have local changes; commit or stash them before automatic deployment"
  fi

  log "Pulling origin/main"
  git -C "$PROJECT_ROOT" pull --ff-only origin main
}

install_system_dependencies() {
  if [[ "$INSTALL_SYSTEM_DEPS" -ne 1 ]]; then
    log "Skipping system dependency installation"
    return
  fi

  [[ -f /etc/os-release ]] || die "/etc/os-release not found"
  # shellcheck disable=SC1091
  source /etc/os-release
  [[ "${ID:-}" == "alinux" && "${VERSION_ID:-}" == "3" ]] || \
    die "Automatic OS package installation supports Alibaba Cloud Linux 3 only"

  if command -v python3.11 >/dev/null 2>&1 && \
     python3.11 -m pip --version >/dev/null 2>&1 && \
     command -v git >/dev/null 2>&1 && \
     command -v curl >/dev/null 2>&1; then
    log "Python 3.11, pip, Git and curl are already installed"
  else
    log "Installing Python 3.11, pip, Git and curl"
    dnf install -y python3.11 python3.11-pip git curl
  fi

  if command -v ffmpeg >/dev/null 2>&1 && command -v ffprobe >/dev/null 2>&1; then
    log "ffmpeg and ffprobe are already installed"
    return
  fi

  log "Trying the enabled repositories for ffmpeg"
  if dnf install -y ffmpeg && \
     command -v ffmpeg >/dev/null 2>&1 && \
     command -v ffprobe >/dev/null 2>&1; then
    return
  fi

  log "Enabling EPEL and RPM Fusion EL8 for ffmpeg"
  if ! dnf install -y epel-release; then
    dnf install -y "$EPEL_RELEASE_URL"
  fi
  dnf install -y "$RPM_FUSION_URL"
  dnf clean metadata
  dnf makecache
  dnf install -y ffmpeg
}

prepare_virtualenv() {
  command -v "$PYTHON_BIN" >/dev/null 2>&1 || die "$PYTHON_BIN is not installed"

  if [[ -x "$VENV_DIR/bin/python" ]] && \
     ! "$VENV_DIR/bin/python" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)'; then
    local old_venv="$BACKEND_DIR/.venv.python-old.$(date +%Y%m%d_%H%M%S)"
    log "Moving incompatible virtualenv to $old_venv"
    mv "$VENV_DIR" "$old_venv"
  fi

  if [[ ! -x "$VENV_DIR/bin/python" ]]; then
    log "Creating Python virtualenv: $VENV_DIR"
    "$PYTHON_BIN" -m venv "$VENV_DIR"
  fi

  log "Installing Python dependencies"
  "$VENV_DIR/bin/python" -m pip install --upgrade pip setuptools wheel \
    --index-url "$PIP_INDEX_URL"
  "$VENV_DIR/bin/python" -m pip install -r "$BACKEND_DIR/requirements.txt" \
    --index-url "$PIP_INDEX_URL"
}

resolve_env_binary() {
  local key="$1"
  local fallback="$2"
  local value
  value="$(sed -n "s/^${key}=//p" "$BACKEND_DIR/.env" | tail -n 1)"
  value="${value%$'\r'}"
  echo "${value:-$fallback}"
}

validate_runtime() {
  local ffmpeg_bin
  local ffprobe_bin

  mkdir -p \
    "$BACKEND_DIR/data/recordings" \
    "$BACKEND_DIR/logs" \
    "$BACKEND_DIR/run" \
    "$BACKEND_DIR/backups"

  "$VENV_DIR/bin/python" -m json.tool "$BACKEND_DIR/config/anchors.json" >/dev/null

  ffmpeg_bin="$(resolve_env_binary FFMPEG_BIN ffmpeg)"
  ffprobe_bin="$(resolve_env_binary FFPROBE_BIN ffprobe)"

  if [[ "$ffmpeg_bin" == */* ]]; then
    [[ -x "$ffmpeg_bin" ]] || die "FFMPEG_BIN is not executable: $ffmpeg_bin"
  else
    command -v "$ffmpeg_bin" >/dev/null 2>&1 || die "ffmpeg command not found: $ffmpeg_bin"
  fi

  if [[ "$ffprobe_bin" == */* ]]; then
    [[ -x "$ffprobe_bin" ]] || die "FFPROBE_BIN is not executable: $ffprobe_bin"
  else
    command -v "$ffprobe_bin" >/dev/null 2>&1 || die "ffprobe command not found: $ffprobe_bin"
  fi

  if [[ "$RUN_TESTS" -eq 1 ]]; then
    log "Running unit tests"
    (
      cd "$BACKEND_DIR"
      "$VENV_DIR/bin/python" -m unittest discover -s tests -v
    )
  else
    log "Skipping tests"
  fi
}

install_systemd_units() {
  local backend_template="$BACKEND_DIR/deploy/systemd/live-record-backend.service"
  local scheduler_template="$BACKEND_DIR/deploy/systemd/live-record-scheduler.service"
  [[ -f "$backend_template" ]] || die "Backend systemd template not found"
  [[ -f "$scheduler_template" ]] || die "Scheduler systemd template not found"

  UNIT_TMP_DIR="$(mktemp -d)"
  sed "s|/opt/live-record/backend|$BACKEND_DIR|g" \
    "$backend_template" > "$UNIT_TMP_DIR/live-record-backend.service"
  sed "s|/opt/live-record/backend|$BACKEND_DIR|g" \
    "$scheduler_template" > "$UNIT_TMP_DIR/live-record-scheduler.service"

  install -m 0644 "$UNIT_TMP_DIR/live-record-backend.service" \
    /etc/systemd/system/live-record-backend.service
  install -m 0644 "$UNIT_TMP_DIR/live-record-scheduler.service" \
    /etc/systemd/system/live-record-scheduler.service

  systemctl daemon-reload
  systemctl enable live-record-backend live-record-scheduler
}

wait_for_backend() {
  local attempt
  for attempt in $(seq 1 20); do
    if curl -fsS http://127.0.0.1:5000/health >/dev/null; then
      return 0
    fi
    sleep 1
  done
  return 1
}

restart_services() {
  if systemctl is-active --quiet live-record-scheduler; then
    log "Stopping scheduler gracefully"
    systemctl stop live-record-scheduler
  fi

  log "Starting backend"
  systemctl restart live-record-backend
  if ! wait_for_backend; then
    journalctl -u live-record-backend -n 100 --no-pager >&2 || true
    die "Backend health check failed"
  fi

  log "Starting scheduler"
  systemctl restart live-record-scheduler
  sleep 2
  systemctl is-active --quiet live-record-scheduler || {
    journalctl -u live-record-scheduler -n 100 --no-pager >&2 || true
    die "Scheduler failed to start"
  }
}

print_summary() {
  local commit
  commit="$(git -C "$PROJECT_ROOT" log -1 --oneline)"
  log "Deployment complete: $commit"
  systemctl --no-pager --full status live-record-backend | sed -n '1,5p'
  systemctl --no-pager --full status live-record-scheduler | sed -n '1,5p'
  echo
  echo "Health:  http://127.0.0.1:5000/health"
  echo "Logs:    journalctl -u live-record-scheduler -f"
  echo "Backups: $BACKEND_DIR/backups/"
}

pull_code
install_system_dependencies
prepare_virtualenv
validate_runtime
install_systemd_units
restart_services
print_summary
