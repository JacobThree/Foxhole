# Release and Upgrade Guide

## Version 0.1.0 (MVP)

### Staged Rollout Validation Checklist
- [x] **Stage 1 (Read-Only):** Answers "what is broken right now?" correctly for Plex buffering, container loops, and Proxmox storage limits.
- [x] **Stage 2 (Confirmed Writes):** Tested container restart and confirmed they require human intervention in UI/Chat.
- [x] **Stage 3 (Autonomous):** Autonomous rules remain disabled by default.

### Upgrade Instructions

#### Docker Compose
1. Pull the new image:
   ```bash
   docker compose -f iac/compose/docker-compose.yml pull
   ```
2. Restart the stack:
   ```bash
   docker compose -f iac/compose/docker-compose.yml up -d
   ```

#### Proxmox LXC / Debian Systemd
1. Navigate to your install directory (e.g., `/opt/homelab-agent`).
2. Pull the latest code:
   ```bash
   git pull origin main
   ```
3. Update dependencies:
   ```bash
   RTK poetry install
   # Or activate virtualenv and run `pip install -e .`
   ```
4. Restart the service:
   ```bash
   sudo systemctl restart homelab-agent
   ```

### Rollback
To rollback, checkout the previous tag (e.g., `git checkout v0.0.9`) and restart the service/containers using the steps above.
