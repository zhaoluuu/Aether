#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

REPO_DIR="/opt/aether/current"
APP_USER="aether"
BLUE_SERVICE_NAME="aether-backend"
GREEN_SERVICE_NAME="aether-backend-green"
BLUE_PORT=8084
GREEN_PORT=8086
BACKUP_DIR="/root/aether-backups"
LOG_DIR="/root/aether-deploy-logs"
NGINX_SITE_CONFIG="/etc/nginx/sites-available/aether"
NGINX_PROXY_INCLUDE="/etc/nginx/conf.d/aether-backend-proxy.inc"
PUBLIC_HEALTH_URL="https://www.hook.rs/v1/health"
LOCAL_HEALTH_PATH="/v1/health"

SKIP_BACKUP=0
SKIP_BACKEND=0
SKIP_FRONTEND=0
TARGET_BRANCH=""
NODE_VERSION="${NODE_VERSION:-22}"

SYSTEMD_RELOAD_NEEDED=0
NGINX_RELOAD_NEEDED=0

usage() {
  cat <<'EOF'
Usage:
  deploy-aether.sh [options]

Options:
  --branch <name>       Deploy a specific git branch. Default: current branch
  --skip-backup         Do not create a PostgreSQL backup before deploy
  --skip-backend        Skip Python dependency update and backend slot switch
  --skip-frontend       Skip frontend npm install and build
  -h, --help            Show this help

Examples:
  deploy-aether.sh
  deploy-aether.sh --branch master
  deploy-aether.sh --skip-frontend
  deploy-aether.sh --skip-backup --skip-backend
EOF
}

log() {
  printf '[%s] %s\n' "$(date '+%F %T')" "$*"
}

fail() {
  log "ERROR: $*"
  exit 1
}

run_as_app() {
  runuser -u "$APP_USER" -- bash -lc "$1"
}

slot_service() {
  case "$1" in
    blue) echo "$BLUE_SERVICE_NAME" ;;
    green) echo "$GREEN_SERVICE_NAME" ;;
    *) fail "Unknown slot: $1" ;;
  esac
}

slot_port() {
  case "$1" in
    blue) echo "$BLUE_PORT" ;;
    green) echo "$GREEN_PORT" ;;
    *) fail "Unknown slot: $1" ;;
  esac
}

other_slot() {
  case "$1" in
    blue) echo "green" ;;
    green) echo "blue" ;;
    *) fail "Unknown slot: $1" ;;
  esac
}

health_url_for_slot() {
  printf 'http://127.0.0.1:%s%s' "$(slot_port "$1")" "$LOCAL_HEALTH_PATH"
}

wait_for_http_ok() {
  local url="$1"
  local label="$2"
  local max_attempts="${3:-15}"
  local delay_seconds="${4:-2}"
  local attempt=1

  while (( attempt <= max_attempts )); do
    if curl -fsS "$url" >/dev/null; then
      log "$label passed (attempt ${attempt}/${max_attempts})"
      return 0
    fi

    if (( attempt == max_attempts )); then
      log "$label failed after ${max_attempts} attempts"
      return 1
    fi

    log "$label not ready yet (attempt ${attempt}/${max_attempts}), retrying in ${delay_seconds}s"
    sleep "$delay_seconds"
    ((attempt++))
  done
}

render_green_service_unit() {
  cat <<EOF
[Unit]
Description=Aether Backend (green slot)
After=network.target postgresql.service redis-server.service
Wants=postgresql.service redis-server.service

[Service]
Type=simple
User=${APP_USER}
Group=${APP_USER}
WorkingDirectory=${REPO_DIR}
EnvironmentFile=${REPO_DIR}/.env
Environment=PATH=${REPO_DIR}/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
Environment=PORT=${GREEN_PORT}
ExecStartPre=/bin/bash -lc 'cd ${REPO_DIR} && set -a && . ./.env && set +a && . .venv/bin/activate && alembic upgrade head'
ExecStart=/bin/bash -lc 'cd ${REPO_DIR} && MAX_REQUESTS_JITTER=$((${MAX_REQUESTS:-50000}/20)); exec gunicorn src.main:app -c gunicorn_conf.py --preload -w ${GUNICORN_WORKERS:-2} -k uvicorn.workers.UvicornWorker --bind 127.0.0.1:${GREEN_PORT} --max-requests ${MAX_REQUESTS:-50000} --max-requests-jitter \$MAX_REQUESTS_JITTER --access-logfile - --error-logfile - --log-level info'
Restart=always
RestartSec=5
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
EOF
}

ensure_green_service_unit() {
  local target="/etc/systemd/system/${GREEN_SERVICE_NAME}.service"
  local tmp
  tmp="$(mktemp)"
  render_green_service_unit > "$tmp"

  if [[ ! -f "$target" ]] || ! cmp -s "$tmp" "$target"; then
    install -m 0644 "$tmp" "$target"
    SYSTEMD_RELOAD_NEEDED=1
    log "Updated systemd unit: $target"
  fi

  rm -f "$tmp"
}

write_proxy_include_for_slot() {
  local slot="$1"
  local port
  port="$(slot_port "$slot")"
  mkdir -p "$(dirname "$NGINX_PROXY_INCLUDE")"
  cat > "$NGINX_PROXY_INCLUDE" <<EOF
proxy_pass http://127.0.0.1:${port};
EOF
  NGINX_RELOAD_NEEDED=1
}

detect_active_slot() {
  if [[ -f "$NGINX_PROXY_INCLUDE" ]]; then
    if grep -q "127.0.0.1:${GREEN_PORT}" "$NGINX_PROXY_INCLUDE"; then
      echo "green"
      return 0
    fi
    if grep -q "127.0.0.1:${BLUE_PORT}" "$NGINX_PROXY_INCLUDE"; then
      echo "blue"
      return 0
    fi
  fi

  if systemctl is-active --quiet "$GREEN_SERVICE_NAME"; then
    echo "green"
  else
    echo "blue"
  fi
}

ensure_switchable_nginx_proxy() {
  if ! grep -qF "include ${NGINX_PROXY_INCLUDE};" "$NGINX_SITE_CONFIG"; then
    python3 - <<PY
from pathlib import Path

path = Path("${NGINX_SITE_CONFIG}")
text = path.read_text()
old = "        proxy_pass http://127.0.0.1:8084;\n"
new = "        include ${NGINX_PROXY_INCLUDE};\n"
if old not in text:
    raise SystemExit("nginx site config does not contain expected proxy_pass line")
path.write_text(text.replace(old, new, 1))
PY
    NGINX_RELOAD_NEEDED=1
    log "Patched nginx site config to use switchable proxy include"
  fi

  if [[ ! -f "$NGINX_PROXY_INCLUDE" ]]; then
    write_proxy_include_for_slot "blue"
    log "Initialized nginx proxy include with blue slot"
  fi
}

reload_if_needed() {
  if [[ "$SYSTEMD_RELOAD_NEEDED" -eq 1 ]]; then
    systemctl daemon-reload
    systemctl enable "$GREEN_SERVICE_NAME" >/dev/null 2>&1 || true
    SYSTEMD_RELOAD_NEEDED=0
    log "Reloaded systemd daemon"
  fi

  if [[ "$NGINX_RELOAD_NEEDED" -eq 1 ]]; then
    nginx -t
    systemctl reload nginx
    NGINX_RELOAD_NEEDED=0
    log "Reloaded nginx"
  fi
}

ensure_rolling_runtime_prerequisites() {
  ensure_green_service_unit
  ensure_switchable_nginx_proxy
  reload_if_needed
}

on_error() {
  local line="$1"
  log "Deploy failed at line ${line}"
  systemctl status "$BLUE_SERVICE_NAME" --no-pager || true
  systemctl status "$GREEN_SERVICE_NAME" --no-pager || true
}

trap 'on_error $LINENO' ERR

while [[ $# -gt 0 ]]; do
  case "$1" in
    --branch)
      [[ $# -ge 2 ]] || fail "--branch requires a value"
      TARGET_BRANCH="$2"
      shift 2
      ;;
    --skip-backup)
      SKIP_BACKUP=1
      shift
      ;;
    --skip-backend)
      SKIP_BACKEND=1
      shift
      ;;
    --skip-frontend)
      SKIP_FRONTEND=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      fail "Unknown argument: $1"
      ;;
  esac
done

[[ ${EUID} -eq 0 ]] || fail "Please run as root"
[[ -d "$REPO_DIR" ]] || fail "Repository directory not found: $REPO_DIR"
id "$APP_USER" >/dev/null 2>&1 || fail "User not found: $APP_USER"

APP_HOME="$(getent passwd "$APP_USER" | cut -d: -f6)"
NVM_SH="${APP_HOME}/.nvm/nvm.sh"
[[ -f "$NVM_SH" ]] || fail "nvm not found: $NVM_SH"

mkdir -p "$BACKUP_DIR" "$LOG_DIR"
TIMESTAMP="$(date '+%F-%H%M%S')"
LOG_FILE="${LOG_DIR}/deploy-${TIMESTAMP}.log"
exec > >(tee -a "$LOG_FILE") 2>&1

log "Deploy started"
log "Repository: $REPO_DIR"

ensure_rolling_runtime_prerequisites

CURRENT_BRANCH="$(run_as_app "cd '$REPO_DIR' && git branch --show-current")"
if [[ -z "$TARGET_BRANCH" ]]; then
  TARGET_BRANCH="$CURRENT_BRANCH"
fi

CURRENT_COMMIT="$(run_as_app "cd '$REPO_DIR' && git rev-parse --short HEAD")"
ACTIVE_SLOT="$(detect_active_slot)"
IDLE_SLOT="$(other_slot "$ACTIVE_SLOT")"

log "Current branch: $CURRENT_BRANCH"
log "Current commit: $CURRENT_COMMIT"
log "Target branch: $TARGET_BRANCH"
log "Active slot: $ACTIVE_SLOT ($(slot_service "$ACTIVE_SLOT"):$(slot_port "$ACTIVE_SLOT"))"
log "Idle slot: $IDLE_SLOT ($(slot_service "$IDLE_SLOT"):$(slot_port "$IDLE_SLOT"))"

run_as_app "cd '$REPO_DIR' && if ! git diff --quiet || ! git diff --cached --quiet; then echo 'Repository has local changes:'; git status --short; exit 1; fi"

BACKUP_FILE=""
if [[ "$SKIP_BACKUP" -eq 0 ]]; then
  BACKUP_FILE="${BACKUP_DIR}/aether-${TIMESTAMP}.sql"
  log "Creating PostgreSQL backup: $BACKUP_FILE"
  runuser -u postgres -- pg_dump aether > "$BACKUP_FILE"
  gzip -f "$BACKUP_FILE"
  BACKUP_FILE="${BACKUP_FILE}.gz"
  log "Backup complete: $BACKUP_FILE"
else
  log "Skipping database backup"
fi

log "Fetching latest code"
run_as_app "cd '$REPO_DIR' && git fetch --all --prune && git checkout '$TARGET_BRANCH' && git pull --ff-only origin '$TARGET_BRANCH'"

NEW_COMMIT="$(run_as_app "cd '$REPO_DIR' && git rev-parse --short HEAD")"
log "Updated to commit: $NEW_COMMIT"

if [[ "$SKIP_BACKEND" -eq 0 ]]; then
  log "Updating Python dependencies"
  run_as_app "cd '$REPO_DIR' && source .venv/bin/activate && pip install -e ."
else
  log "Skipping backend dependency update"
fi

if [[ "$SKIP_FRONTEND" -eq 0 ]]; then
  log "Installing frontend dependencies and building"
  run_as_app "cd '$REPO_DIR/frontend' && source '$NVM_SH' && nvm use '$NODE_VERSION' >/dev/null && npm install && npm run build"
else
  log "Skipping frontend build"
fi

if [[ "$SKIP_BACKEND" -eq 0 ]]; then
  local_idle_service="$(slot_service "$IDLE_SLOT")"
  local_idle_url="$(health_url_for_slot "$IDLE_SLOT")"

  log "Restarting idle slot service: ${local_idle_service}"
  systemctl restart "$local_idle_service"
  systemctl is-active "$local_idle_service" >/dev/null
  log "Idle slot service is active"

  log "Checking idle slot health endpoint"
  wait_for_http_ok "$local_idle_url" "Idle slot health check (${IDLE_SLOT})" 20 2

  log "Switching nginx traffic to ${IDLE_SLOT} slot"
  write_proxy_include_for_slot "$IDLE_SLOT"
  reload_if_needed

  log "Checking public health endpoint after slot switch"
  wait_for_http_ok "$PUBLIC_HEALTH_URL" "Public health check" 15 2

  ACTIVE_SLOT="$IDLE_SLOT"
  IDLE_SLOT="$(other_slot "$ACTIVE_SLOT")"
  log "Traffic switched successfully; standby slot remains online: $IDLE_SLOT"
else
  log "Skipping backend slot switch"
fi

log "Recent backend logs (${BLUE_SERVICE_NAME})"
journalctl -u "$BLUE_SERVICE_NAME" -n 30 --no-pager || true
log "Recent backend logs (${GREEN_SERVICE_NAME})"
journalctl -u "$GREEN_SERVICE_NAME" -n 30 --no-pager || true

log "Deploy finished successfully"
log "Log file: $LOG_FILE"
if [[ -n "$BACKUP_FILE" ]]; then
  log "Backup file: $BACKUP_FILE"
fi
