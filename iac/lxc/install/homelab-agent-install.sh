#!/usr/bin/env bash
set -euo pipefail

AGENT_USER="${AGENT_USER:-agent}"
INSTALL_DIR="${INSTALL_DIR:-/opt/homelab-agent}"
CONFIG_DIR="${CONFIG_DIR:-/etc/homelab-agent}"
SERVICE_FILE="${SERVICE_FILE:-/tmp/foxhole-install/homelab-agent.service}"
FOXHOLE_REPO_URL="${FOXHOLE_REPO_URL:-}"
FOXHOLE_REF="${FOXHOLE_REF:-main}"

export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y --no-install-recommends \
  build-essential \
  ca-certificates \
  curl \
  docker.io \
  git \
  nmap \
  python3 \
  python3-dev \
  python3-pip \
  python3-venv

if ! id "${AGENT_USER}" >/dev/null 2>&1; then
  useradd --system --create-home --home-dir "${INSTALL_DIR}" --shell /usr/sbin/nologin "${AGENT_USER}"
fi

install -d -o "${AGENT_USER}" -g "${AGENT_USER}" -m 0750 "${INSTALL_DIR}"
install -d -o root -g "${AGENT_USER}" -m 0750 "${CONFIG_DIR}"

if [[ ! -f "${CONFIG_DIR}/foxhole.env" ]]; then
  install -o root -g "${AGENT_USER}" -m 0640 /dev/null "${CONFIG_DIR}/foxhole.env"
fi

if [[ -n "${FOXHOLE_REPO_URL}" ]]; then
  if [[ -d "${INSTALL_DIR}/source/.git" ]]; then
    git -C "${INSTALL_DIR}/source" fetch --depth 1 origin "${FOXHOLE_REF}"
    git -C "${INSTALL_DIR}/source" checkout FETCH_HEAD
  else
    git clone --depth 1 --branch "${FOXHOLE_REF}" "${FOXHOLE_REPO_URL}" "${INSTALL_DIR}/source"
  fi
elif [[ -d /tmp/foxhole-src ]]; then
  rm -rf "${INSTALL_DIR}/source"
  cp -a /tmp/foxhole-src "${INSTALL_DIR}/source"
else
  install -d -o "${AGENT_USER}" -g "${AGENT_USER}" "${INSTALL_DIR}/source"
fi

chown -R "${AGENT_USER}:${AGENT_USER}" "${INSTALL_DIR}"
python3 -m venv "${INSTALL_DIR}/venv"
"${INSTALL_DIR}/venv/bin/python" -m pip install --upgrade pip

if [[ -f "${INSTALL_DIR}/source/pyproject.toml" ]]; then
  "${INSTALL_DIR}/venv/bin/python" -m pip install "${INSTALL_DIR}/source"
else
  echo "No source package found. Set FOXHOLE_REPO_URL or copy source to /tmp/foxhole-src, then rerun." >&2
fi

install -D -m 0644 "${SERVICE_FILE}" /etc/systemd/system/homelab-agent.service
systemctl daemon-reload
systemctl enable homelab-agent.service

echo "Installed Foxhole service. Configure ${CONFIG_DIR}/foxhole.env, then run: systemctl start homelab-agent"

