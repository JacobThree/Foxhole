# Storage and Backups Runbook

## Overview
This runbook describes how Foxhole monitors Proxmox datastores and backup job statuses.

## What Foxhole Checks (Read-Only)
Foxhole's storage monitoring looks at:
1. **Proxmox Datastores:** Scans all configured datastores across nodes to report `used`, `total`, and `percentage`.
2. **Thresholds:** Checks if any datastore exceeds the user-configured usage threshold (default 80%).
3. **Backup Jobs (VZDump):** Inspects the `/var/log/pve/tasks` (or API equivalent) for recent `vzdump` task statuses to detect failed backups.

## Manual Actions Required
If storage is full, you must manually free space (e.g., deleting old ISOs, pruning old backups, or expanding the logical volume). Foxhole will not autonomously delete data. If a backup failed due to locked files or storage unavailability, you must investigate the target storage medium.

## Example Prompts
- *"Is my Proxmox storage running out of space?"*
- *"Did the nightly Proxmox backups succeed?"*
- *"Check the health of the `local-lvm` datastore."*
