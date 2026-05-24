# Proxmox LXC Install

The LXC path creates an unprivileged Debian 12 container by default and installs Foxhole as the `agent` system user.

Run on a Proxmox node:

```bash
sudo iac/lxc/install-homelab-agent.sh
```

Default bootstrap variables:

```text
CTID=240
HOSTNAME=foxhole
CPU=2
RAM=2048
DISK=8
OS=debian
VERSION=12
UNPRIVILEGED=1
TAGS=homelab;foxhole
STORAGE=local-lvm
TEMPLATE_STORAGE=local
BRIDGE=vmbr0
```

Override them inline when needed:

```bash
sudo CTID=241 RAM=4096 DISK=16 iac/lxc/install-homelab-agent.sh
```

The inside-container installer:

- Installs Python, venv tooling, Docker client dependencies, `nmap`, curl, and git.
- Creates `/opt/homelab-agent`, `/opt/homelab-agent/data`, and `/etc/homelab-agent`.
- Installs the prebuilt static dashboard into `/opt/homelab-agent/ui/out`.
- Creates an unprivileged `agent` service user.
- Installs `homelab-agent.service` with systemd hardening.
- Reads runtime configuration from `/etc/homelab-agent/foxhole.env`.
- Writes API or dashboard settings updates back to `/etc/homelab-agent/foxhole.env`.

`homelab-agent.service` runs the default single-process Foxhole runtime. One service serves the static dashboard, API, in-process scheduler, in-memory live events, and SQLite-backed history on port `8000`; Redis, Celery worker, and Celery beat are not required for the default LXC install. Durable history is stored at `/opt/homelab-agent/data/foxhole.db` unless `FOXHOLE_DATABASE_PATH` is overridden in the env file.

Use distributed mode only for advanced installs that intentionally run separate Redis/Celery services. In that case, set `FOXHOLE_RUNTIME_MODE=distributed` and `FOXHOLE_REDIS_URL=...` in `/etc/homelab-agent/foxhole.env`, then provision the Redis, worker, and beat processes separately.

Build the dashboard before running the Proxmox installer from this repository. The installer packages `ui/out` and pushes it into the container; if it is missing, the in-container install fails instead of deploying an API-only service:

```bash
cd ui
pnpm install
pnpm build
cd ..
```

The service file sets `FOXHOLE_STATIC_UI_DIR=/opt/homelab-agent/ui/out`, so FastAPI serves the dashboard from the copied export instead of requiring Node.js in the container.

Set `FOXHOLE_REPO_URL` when running the installer if the source is not copied into `/tmp/foxhole-src`:

```bash
sudo FOXHOLE_REPO_URL=https://github.com/<owner>/<repo>.git iac/lxc/install-homelab-agent.sh
```

After the container is created, fill `/etc/homelab-agent/foxhole.env` inside the container and start the service:

```bash
pct exec 240 -- editor /etc/homelab-agent/foxhole.env
pct exec 240 -- systemctl start homelab-agent
```

Minimum first-run values:

```env
FOXHOLE_API_BEARER_TOKEN=change-me
FOXHOLE_SESSION_COOKIE_SECURE=false
```

Keep `FOXHOLE_SESSION_COOKIE_SECURE=false` for direct HTTP access to the LXC. Set it to `true` when Foxhole is served through HTTPS.

## Backup And Restore

Back up these paths inside the container:

```text
/etc/homelab-agent/foxhole.env
/opt/homelab-agent/data/
```

The env file contains secrets and UI-edited settings. The data directory contains `foxhole.db` and any SQLite sidecar files. If `FOXHOLE_DATABASE_PATH` is overridden, back up that configured database path instead of `/opt/homelab-agent/data/`.

Create a backup from the Proxmox node:

```bash
pct exec 240 -- systemctl stop homelab-agent
pct exec 240 -- tar -C / -czf /tmp/foxhole-backup.tgz etc/homelab-agent/foxhole.env opt/homelab-agent/data
pct pull 240 /tmp/foxhole-backup.tgz ./foxhole-lxc-240-$(date +%Y%m%d-%H%M%S).tgz
pct exec 240 -- rm -f /tmp/foxhole-backup.tgz
pct exec 240 -- systemctl start homelab-agent
```

Restore to an installed container:

```bash
pct exec 240 -- systemctl stop homelab-agent
pct push 240 ./foxhole-lxc-240-YYYYMMDD-HHMMSS.tgz /tmp/foxhole-backup.tgz -perms 0600
pct exec 240 -- tar -C / -xzf /tmp/foxhole-backup.tgz
pct exec 240 -- chown -R agent:agent /opt/homelab-agent/data
pct exec 240 -- chown root:agent /etc/homelab-agent/foxhole.env
pct exec 240 -- chmod 0660 /etc/homelab-agent/foxhole.env
pct exec 240 -- rm -f /tmp/foxhole-backup.tgz
pct exec 240 -- systemctl start homelab-agent
```

The bootstrap does not require privileged container mode by default. Keep `UNPRIVILEGED=1` unless a future diagnostic tool has a specific, documented need.
