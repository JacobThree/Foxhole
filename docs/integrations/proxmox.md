# Proxmox Integration

Foxhole uses a dedicated Proxmox API token. Stage 1 tools are read-only and are expected to work with the audit role from `docs/deployment/proxmox-permissions.md`.

Configure:

```bash
FOXHOLE_PROXMOX_HOST=pve.example.test
FOXHOLE_PROXMOX_TOKEN_ID=homelab-agent@pve!foxhole
FOXHOLE_PROXMOX_TOKEN_SECRET=secret
FOXHOLE_PROXMOX_VERIFY_SSL=true
```

Available tools:

- `proxmox_node_status`
- `proxmox_inventory`
- `proxmox_storage_usage`
- `proxmox_backup_jobs`
- `proxmox_migrate_lxc`

Storage diagnostics include datastore type, enabled state, used percent, used GB, and total GB. `proxmox_migrate_lxc` requires Stage 2 privileges, `VM.Migrate`, and explicit confirmation through the write policy.
