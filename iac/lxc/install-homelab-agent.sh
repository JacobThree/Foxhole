#!/usr/bin/env bash
set -euo pipefail

CTID="${CTID:-240}"
HOSTNAME="${HOSTNAME:-foxhole}"
CPU="${CPU:-2}"
RAM="${RAM:-2048}"
DISK="${DISK:-8}"
OS="${OS:-debian}"
VERSION="${VERSION:-12}"
UNPRIVILEGED="${UNPRIVILEGED:-1}"
TAGS="${TAGS:-homelab;foxhole}"
STORAGE="${STORAGE:-local-lvm}"
TEMPLATE_STORAGE="${TEMPLATE_STORAGE:-local}"
BRIDGE="${BRIDGE:-vmbr0}"
INSTALLER_PATH="${INSTALLER_PATH:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/install/homelab-agent-install.sh}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
STATIC_UI_ARCHIVE="${STATIC_UI_ARCHIVE:-/tmp/foxhole-ui-out.tgz}"

require_root() {
  if [[ "$(id -u)" -ne 0 ]]; then
    echo "Run this script as root on a Proxmox node." >&2
    exit 1
  fi
}

template_name() {
  pveam available --section system | awk -v os="${OS}-${VERSION}" '$2 ~ os { print $2 }' | tail -n 1
}

require_root

if pct status "${CTID}" >/dev/null 2>&1; then
  echo "Container ${CTID} already exists." >&2
  exit 1
fi

TEMPLATE="$(template_name)"
if [[ -z "${TEMPLATE}" ]]; then
  echo "No ${OS} ${VERSION} template found in pveam output." >&2
  exit 1
fi

if [[ ! -f "/var/lib/vz/template/cache/${TEMPLATE}" ]]; then
  pveam download "${TEMPLATE_STORAGE}" "${TEMPLATE}"
fi

pct create "${CTID}" "${TEMPLATE_STORAGE}:vztmpl/${TEMPLATE}" \
  --hostname "${HOSTNAME}" \
  --cores "${CPU}" \
  --memory "${RAM}" \
  --rootfs "${STORAGE}:${DISK}" \
  --ostype "${OS}" \
  --unprivileged "${UNPRIVILEGED}" \
  --features nesting=1 \
  --net0 "name=eth0,bridge=${BRIDGE},ip=dhcp" \
  --tags "${TAGS}" \
  --start 1

echo "Waiting for container ${CTID} to boot."
sleep 10

pct exec "${CTID}" -- mkdir -p /tmp/foxhole-install
pct push "${CTID}" "${INSTALLER_PATH}" /tmp/foxhole-install/homelab-agent-install.sh -perms 0755
pct push "${CTID}" "${SCRIPT_DIR}/systemd/homelab-agent.service" \
  /tmp/foxhole-install/homelab-agent.service -perms 0644

if [[ -f "${SOURCE_ROOT}/ui/out/index.html" ]]; then
  tar -C "${SOURCE_ROOT}/ui/out" -czf "${STATIC_UI_ARCHIVE}" .
  pct push "${CTID}" "${STATIC_UI_ARCHIVE}" /tmp/foxhole-install/ui-out.tgz -perms 0644
else
  echo "Static dashboard build not found at ${SOURCE_ROOT}/ui/out."
  echo "Run 'cd ${SOURCE_ROOT}/ui && pnpm install && pnpm build' before this installer to include the dashboard."
fi

pct exec "${CTID}" -- bash /tmp/foxhole-install/homelab-agent-install.sh

echo "Container ${CTID} is ready. Add /etc/homelab-agent/foxhole.env values before starting the service."
