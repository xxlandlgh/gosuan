#!/usr/bin/env bash
set -Eeuo pipefail

APP_NAME="${APP_NAME:-gosuan}"
APP_USER="${APP_USER:-root}"
APP_GROUP="${APP_GROUP:-$APP_USER}"
APP_DIR="${APP_DIR:-/opt/gosuan}"
REPO_URL="${REPO_URL:-https://github.com/xxlandlgh/gosuan.git}"
BRANCH="${BRANCH:-main}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-$APP_DIR/.venv}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"
DOMAIN="${DOMAIN:-_}"
ENABLE_NGINX="${ENABLE_NGINX:-1}"
ENABLE_FIREWALL="${ENABLE_FIREWALL:-0}"

log() {
  printf '\n[%s] %s\n' "$(date '+%F %T')" "$*"
}

require_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    echo "请使用 root 或 sudo 运行此脚本"
    exit 1
  fi
}

install_system_packages() {
  log "安装系统依赖"
  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  apt-get install -y \
    git \
    curl \
    nginx \
    "${PYTHON_BIN}" \
    python3-venv \
    python3-pip
  if [[ "${ENABLE_FIREWALL}" == "1" ]]; then
    apt-get install -y ufw
  fi
}

ensure_app_user() {
  if ! id -u "${APP_USER}" >/dev/null 2>&1; then
    log "创建运行用户 ${APP_USER}"
    useradd --system --create-home --shell /bin/bash "${APP_USER}"
  fi
}

fetch_code() {
  log "拉取代码到 ${APP_DIR}"
  mkdir -p "$(dirname "${APP_DIR}")"
  if [[ -d "${APP_DIR}/.git" ]]; then
    git -C "${APP_DIR}" fetch origin
    git -C "${APP_DIR}" checkout "${BRANCH}"
    git -C "${APP_DIR}" reset --hard "origin/${BRANCH}"
  else
    rm -rf "${APP_DIR}"
    git clone --branch "${BRANCH}" "${REPO_URL}" "${APP_DIR}"
  fi
  chown -R "${APP_USER}:${APP_GROUP}" "${APP_DIR}"
}

setup_python_env() {
  log "创建虚拟环境并安装依赖"
  "${PYTHON_BIN}" -m venv "${VENV_DIR}"
  "${VENV_DIR}/bin/pip" install --upgrade pip
  "${VENV_DIR}/bin/pip" install .
}

write_env_file() {
  log "写入运行环境配置"
  cat > "${APP_DIR}/.env.local" <<EOF
GOSUAN_AI_ENABLED=${GOSUAN_AI_ENABLED:-false}
GOSUAN_AI_BASE_URL=${GOSUAN_AI_BASE_URL:-}
GOSUAN_AI_MODEL=${GOSUAN_AI_MODEL:-}
GOSUAN_AI_API_KEY=${GOSUAN_AI_API_KEY:-}
GOSUAN_AI_TEMPERATURE=${GOSUAN_AI_TEMPERATURE:-0.7}
GOSUAN_AI_MAX_OUTPUT_TOKENS=${GOSUAN_AI_MAX_OUTPUT_TOKENS:-900}
GOSUAN_AI_TIMEOUT_S=${GOSUAN_AI_TIMEOUT_S:-30}
GOSUAN_API_HOST=${HOST}
GOSUAN_API_PORT=${PORT}
EOF
  chown "${APP_USER}:${APP_GROUP}" "${APP_DIR}/.env.local"
  chmod 600 "${APP_DIR}/.env.local"
}

write_systemd_service() {
  log "写入 systemd 服务"
  cat > "/etc/systemd/system/${APP_NAME}.service" <<EOF
[Unit]
Description=gosuan FastAPI service
After=network.target

[Service]
Type=simple
User=${APP_USER}
Group=${APP_GROUP}
WorkingDirectory=${APP_DIR}
Environment=PYTHONUNBUFFERED=1
ExecStart=${VENV_DIR}/bin/python -m gosuan.api
Restart=always
RestartSec=3
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
EOF
  systemctl daemon-reload
  systemctl enable "${APP_NAME}"
  systemctl restart "${APP_NAME}"
}

write_nginx_config() {
  if [[ "${ENABLE_NGINX}" != "1" ]]; then
    log "跳过 nginx 配置"
    return
  fi
  log "写入 nginx 反向代理配置"
  cat > "/etc/nginx/sites-available/${APP_NAME}.conf" <<EOF
server {
    listen 80;
    server_name ${DOMAIN};

    client_max_body_size 20m;

    location / {
        proxy_pass http://${HOST}:${PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 120s;
    }
}
EOF
  ln -sf "/etc/nginx/sites-available/${APP_NAME}.conf" "/etc/nginx/sites-enabled/${APP_NAME}.conf"
  rm -f /etc/nginx/sites-enabled/default
  nginx -t
  systemctl enable nginx
  systemctl restart nginx
}

configure_firewall() {
  if [[ "${ENABLE_FIREWALL}" != "1" ]]; then
    return
  fi
  log "配置防火墙"
  ufw allow OpenSSH
  ufw allow 'Nginx Full'
  ufw --force enable
}

health_check() {
  log "执行健康检查"
  sleep 2
  curl -fsS "http://${HOST}:${PORT}/health"
  if [[ "${ENABLE_NGINX}" == "1" ]]; then
    curl -fsS "http://127.0.0.1/health"
  fi
}

show_result() {
  log "部署完成"
  echo "代码目录: ${APP_DIR}"
  echo "服务名称: ${APP_NAME}"
  echo "应用监听: http://${HOST}:${PORT}"
  if [[ "${ENABLE_NGINX}" == "1" ]]; then
    echo "Nginx 入口: http://${DOMAIN}"
  fi
  echo "查看服务状态: systemctl status ${APP_NAME}"
  echo "查看应用日志: journalctl -u ${APP_NAME} -f"
}

main() {
  require_root
  install_system_packages
  ensure_app_user
  fetch_code
  setup_python_env
  write_env_file
  write_systemd_service
  write_nginx_config
  configure_firewall
  health_check
  show_result
}

main "$@"
