#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CONFIG_FILE="${1:-"$ROOT_DIR/ops/config/yuanxiao.env"}"

if [[ ! -f "$CONFIG_FILE" ]]; then
  echo "Missing config: $CONFIG_FILE"
  echo "Copy ops/config/yuanxiao.env.example to ops/config/yuanxiao.env and fill private values first."
  exit 1
fi

set -a
# shellcheck source=/dev/null
source "$CONFIG_FILE"
set +a

required_vars=(
  YUANXIAO_RELAY_HOST
  YUANXIAO_RELAY_SSH_USER
  YUANXIAO_RELAY_SSH_KEY
  YUANXIAO_DEPLOY_DIR
  YUANXIAO_SYSTEMD_ENV_DIR
  YUANXIAO_SERVICE_USER
  YUANXIAO_SERVICE_GROUP
  YUANXIAO_TLS_COMMON_NAME
  YUANXIAO_TLS_SAN
  YUANXIAO_PORT
  YUANXIAO_HERMES_BRIDGE_URL
)

for var_name in "${required_vars[@]}"; do
  if [[ -z "${!var_name:-}" ]]; then
    echo "Missing required config value: $var_name"
    exit 1
  fi
done

REMOTE="${YUANXIAO_RELAY_SSH_USER}@${YUANXIAO_RELAY_HOST}"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

render_template() {
  local input="$1"
  local output="$2"
  python3 - "$input" "$output" <<'PY'
import os
import sys
from pathlib import Path

source = Path(sys.argv[1]).read_text()
for key, value in os.environ.items():
    source = source.replace(f"__{key}__", value)
    source = source.replace(f"${{{key}}}", value)
Path(sys.argv[2]).write_text(source)
PY
}

render_template "$ROOT_DIR/server/yuanxiao-server/server-san.cnf.template" "$TMP_DIR/server-san.cnf"
render_template "$ROOT_DIR/ops/systemd/yuanxiao.service.template" "$TMP_DIR/yuanxiao.service"

cat > "$TMP_DIR/yuanxiao.env" <<EOF
YUANXIAO_HOST=${YUANXIAO_HOST:-}
YUANXIAO_PORT=${YUANXIAO_PORT}
YUANXIAO_CERT_FILE=${YUANXIAO_CERT_FILE:-$YUANXIAO_DEPLOY_DIR/certs/server.crt}
YUANXIAO_KEY_FILE=${YUANXIAO_KEY_FILE:-$YUANXIAO_DEPLOY_DIR/certs/server.key}
YUANXIAO_HERMES_BRIDGE_URL=${YUANXIAO_HERMES_BRIDGE_URL}
YUANXIAO_HERMES_BRIDGE_TIMEOUT_SECONDS=${YUANXIAO_HERMES_BRIDGE_TIMEOUT_SECONDS:-900}
YUANXIAO_MAX_REQUEST_BYTES=${YUANXIAO_MAX_REQUEST_BYTES:-6000000}
YUANXIAO_KEEPALIVE_INTERVAL_SECONDS=${YUANXIAO_KEEPALIVE_INTERVAL_SECONDS:-10}
YUANXIAO_TLS_HANDSHAKE_TIMEOUT_SECONDS=${YUANXIAO_TLS_HANDSHAKE_TIMEOUT_SECONDS:-5}
YUANXIAO_REQUEST_SOCKET_TIMEOUT_SECONDS=${YUANXIAO_REQUEST_SOCKET_TIMEOUT_SECONDS:-960}
YUANXIAO_INBOX_FILE=${YUANXIAO_INBOX_FILE:-$YUANXIAO_DEPLOY_DIR/data/app_inbox.jsonl}
YUANXIAO_MAX_INBOX_MESSAGES=${YUANXIAO_MAX_INBOX_MESSAGES:-200}
YUANXIAO_ADMIN_TOKEN=${YUANXIAO_ADMIN_TOKEN:-}
EOF

cp "$ROOT_DIR/server/yuanxiao-server/yuanxiao_server.py" "$TMP_DIR/yuanxiao_server.py"

ssh -i "$YUANXIAO_RELAY_SSH_KEY" "$REMOTE" \
  "mkdir -p /tmp/yuanxiao-deploy"
scp -i "$YUANXIAO_RELAY_SSH_KEY" \
  "$TMP_DIR/yuanxiao_server.py" \
  "$TMP_DIR/server-san.cnf" \
  "$TMP_DIR/yuanxiao.service" \
  "$TMP_DIR/yuanxiao.env" \
  "$REMOTE:/tmp/yuanxiao-deploy/"

ssh -i "$YUANXIAO_RELAY_SSH_KEY" "$REMOTE" bash -s -- \
  "$YUANXIAO_DEPLOY_DIR" \
  "$YUANXIAO_SYSTEMD_ENV_DIR" \
  "$YUANXIAO_SERVICE_USER" \
  "$YUANXIAO_SERVICE_GROUP" <<'REMOTE'
set -euo pipefail

DEPLOY_DIR="$1"
SYSTEMD_ENV_DIR="$2"
SERVICE_USER="$3"
SERVICE_GROUP="$4"
UPLOAD_DIR="/tmp/yuanxiao-deploy"

if ! id -u "$SERVICE_USER" >/dev/null 2>&1; then
  sudo useradd --system --home-dir "$DEPLOY_DIR" --shell /usr/sbin/nologin "$SERVICE_USER"
fi

sudo install -d -m 755 -o root -g root "$DEPLOY_DIR"
sudo install -d -m 750 -o "$SERVICE_USER" -g "$SERVICE_GROUP" "$DEPLOY_DIR/certs" "$DEPLOY_DIR/data"
sudo install -d -m 755 -o root -g root "$SYSTEMD_ENV_DIR"
sudo install -m 755 -o root -g root "$UPLOAD_DIR/yuanxiao_server.py" "$DEPLOY_DIR/yuanxiao_server.py"
sudo install -m 600 -o root -g root "$UPLOAD_DIR/yuanxiao.env" "$SYSTEMD_ENV_DIR/yuanxiao.env"

sudo openssl req -x509 -nodes -newkey rsa:2048 -days 3650 \
  -keyout "$DEPLOY_DIR/certs/server.key" \
  -out "$DEPLOY_DIR/certs/server.crt" \
  -config "$UPLOAD_DIR/server-san.cnf" \
  -extensions server_ext
sudo chown "$SERVICE_USER:$SERVICE_GROUP" "$DEPLOY_DIR/certs/server.key" "$DEPLOY_DIR/certs/server.crt"
sudo chmod 600 "$DEPLOY_DIR/certs/server.key"
sudo chmod 644 "$DEPLOY_DIR/certs/server.crt"

sudo install -m 644 -o root -g root "$UPLOAD_DIR/yuanxiao.service" /etc/systemd/system/yuanxiao.service
sudo systemctl daemon-reload
sudo systemctl enable --now yuanxiao.service
sudo systemctl status yuanxiao.service --no-pager -n 20
REMOTE

echo "YuanXiao server deployed to $REMOTE without committing private config."
