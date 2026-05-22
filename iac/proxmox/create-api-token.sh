#!/usr/bin/env bash
set -euo pipefail

USER_ID="${FOXHOLE_PROXMOX_USER:-homelab-agent@pve}"
ROLE_ID="${FOXHOLE_PROXMOX_ROLE:-HomelabAgent}"
TOKEN_NAME="${FOXHOLE_PROXMOX_TOKEN_NAME:-foxhole}"
ACL_PATH="${FOXHOLE_PROXMOX_ACL_PATH:-/}"
ALLOW_MIGRATE="${FOXHOLE_PROXMOX_ALLOW_MIGRATE:-false}"

require_root() {
  if [[ "$(id -u)" -ne 0 ]]; then
    echo "Run this script as root on a Proxmox node." >&2
    exit 1
  fi
}

role_exists() {
  pveum role list | awk '{print $1}' | grep -qx "${ROLE_ID}"
}

user_exists() {
  pveum user list | awk '{print $1}' | grep -qx "${USER_ID}"
}

token_exists() {
  pveum user token list "${USER_ID}" | awk '{print $1}' | grep -qx "${TOKEN_NAME}"
}

privileges() {
  local privs="Sys.Audit VM.Audit Datastore.Audit SDN.Audit"
  if [[ "${ALLOW_MIGRATE}" == "true" ]]; then
    privs="${privs} VM.Migrate"
  fi
  echo "${privs}"
}

require_root

if role_exists; then
  pveum role modify "${ROLE_ID}" -privs "$(privileges)"
else
  pveum role add "${ROLE_ID}" -privs "$(privileges)"
fi

if user_exists; then
  pveum user modify "${USER_ID}" --comment "Foxhole read-only homelab diagnostics"
else
  pveum user add "${USER_ID}" --comment "Foxhole read-only homelab diagnostics"
fi

pveum acl modify "${ACL_PATH}" -user "${USER_ID}" -role "${ROLE_ID}"

if token_exists; then
  pveum user token modify "${USER_ID}" "${TOKEN_NAME}" --privsep 0
  echo "Updated token metadata for ${USER_ID}!${TOKEN_NAME}."
  echo "Proxmox only prints token secrets when a token is created. Rotate the token if the secret is lost."
else
  echo "Creating token ${USER_ID}!${TOKEN_NAME}. Save the printed value immediately."
  pveum user token add "${USER_ID}" "${TOKEN_NAME}" --privsep 0 --comment "Foxhole API token"
fi

cat <<EOF

Environment names:
  FOXHOLE_PROXMOX_TOKEN_ID=${USER_ID}!${TOKEN_NAME}
  FOXHOLE_PROXMOX_TOKEN_SECRET=<value printed by pveum when created>

Avoid placing the token secret directly in shell history. Prefer editing
/etc/homelab-agent/foxhole.env with a local editor or using a password manager.
EOF

