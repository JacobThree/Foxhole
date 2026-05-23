# Foxhole Homelab Agent

Foxhole is an open-source, modular homelab management agent designed for self-hosters. It can inspect, diagnose, and eventually remediate common problems across your homelab stack.

Foxhole explicitly targets the most popular tools deployed on a homeserver: Proxmox, Docker, Portainer, Plex, Sonarr, Radarr, Tautulli, Overseerr, Pi-hole, and Unbound. It treats every integration as an opt-in plugin, ensuring the agent remains lean and correctly scoped to the services you actually run.

## The Safety Model: Read-only First

Foxhole strictly enforces a phased capability model:
1. **Stage 1 (Read-Only)**: Inspects logs, queues, storage, and health. It cannot mutate your server state.
2. **Stage 2 (Confirmed Writes)**: Can perform gated actions (e.g., restarting a Docker container, migrating a Proxmox LXC) only after you explicitly confirm the operation.
3. **Stage 3 (Autonomous Remediation)**: Narrow, disabled-by-default rules that allow the agent to remediate known issues automatically (e.g., rebooting a container in a crash loop).

## What it does

- Analyzes Docker containers, Portainer stacks, and logs.
- Monitors Proxmox storage, backup jobs, and LXC/VM status.
- Diagnoses Plex buffering and database locks.
- Investigates Sonarr/Radarr import failures and queue issues.
- Checks network health via Pi-hole and Unbound.
- Discovers unknown MAC addresses on your LAN.

## What it does NOT do (Yet)

- Broad automated writes: The agent will not blindly wipe media profiles or arbitrarily delete containers.
- Expose the Docker socket directly: All Docker access is securely routed through a read-only socket proxy.

## Getting Started

Foxhole can be deployed via:
- Docker Compose (Recommended)
- Proxmox LXC 
- Debian/Ubuntu Systemd service

Copy `.env.example` to `.env` and fill in your details to start using Foxhole in read-only mode.
