# Backup And Storage Health

`backup_storage_health` combines Proxmox storage usage, Proxmox backup job state, and optional local filesystem checks into one read-only summary.

The tool reports:

- Datastores above the configured usage threshold.
- Backup jobs with failed last-run state.
- Backup jobs older than `stale_after_hours`.
- Optional local filesystems above the configured threshold.

Example arguments:

```json
{
  "max_used_percent": 85,
  "stale_after_hours": 36,
  "datastore_thresholds": {
    "backup": 80
  },
  "local_paths": ["/var/log", "/opt/homelab-agent"]
}
```

The output includes observed evidence and next actions. It does not prune backups, delete files, or change schedules.
