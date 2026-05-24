# Debian and Ubuntu Install

Use this path for a regular Debian 12 or Ubuntu LTS server when Proxmox LXC bootstrap is not needed.

## Ansible

Edit `iac/ansible/inventory.yml`, then run:

```bash
ansible-playbook --syntax-check iac/ansible/playbook.yml
ansible-playbook -i iac/ansible/inventory.yml iac/ansible/playbook.yml
```

The playbook installs Python, venv tooling, Docker client dependencies, `nmap`, and the Foxhole package. It creates the same service user and directories as the LXC installer:

```text
User: agent
Install directory: /opt/homelab-agent
Data directory: /opt/homelab-agent/data
Config directory: /etc/homelab-agent
Env file: /etc/homelab-agent/foxhole.env
```

The env file is created empty and never overwritten by Ansible. Add secrets on the target host after provisioning. Settings changed through the API or dashboard are written back to `/etc/homelab-agent/foxhole.env`.

The installed `homelab-agent.service` runs the default single-process Foxhole runtime. One systemd service serves the dashboard, API, in-process scheduler, and SQLite-backed history on port `8000`; Redis, Celery worker, and Celery beat are optional distributed-mode additions, not default dependencies. Durable history is stored at `/opt/homelab-agent/data/foxhole.db` unless `FOXHOLE_DATABASE_PATH` is overridden in the env file.

## Manual Fallback

On Debian 12 or Ubuntu LTS:

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip python3-dev build-essential git curl nmap docker.io
sudo useradd --system --create-home --home-dir /opt/homelab-agent --shell /usr/sbin/nologin agent
sudo install -d -o agent -g agent -m 0750 /opt/homelab-agent
sudo install -d -o agent -g agent -m 0750 /opt/homelab-agent/data
sudo install -d -o root -g agent -m 0770 /etc/homelab-agent
sudo install -o root -g agent -m 0660 /dev/null /etc/homelab-agent/foxhole.env
sudo python3 -m venv /opt/homelab-agent/venv
sudo /opt/homelab-agent/venv/bin/python -m pip install --upgrade pip
sudo /opt/homelab-agent/venv/bin/python -m pip install /path/to/foxhole
sudo install -m 0644 iac/lxc/systemd/homelab-agent.service /etc/systemd/system/homelab-agent.service
sudo systemctl daemon-reload
sudo systemctl enable homelab-agent
```

Fill `/etc/homelab-agent/foxhole.env`, then start:

```bash
sudo systemctl start homelab-agent
```

Minimum first-run values:

```env
FOXHOLE_API_BEARER_TOKEN=change-me
FOXHOLE_SESSION_COOKIE_SECURE=false
```

Use distributed mode only for advanced installs that intentionally run separate Redis/Celery services. In that case, set `FOXHOLE_RUNTIME_MODE=distributed` and `FOXHOLE_REDIS_URL=...`, then provision Redis, Celery worker, and Celery beat separately.

## Backup And Restore

Back up these paths:

```text
/etc/homelab-agent/foxhole.env
/opt/homelab-agent/data/
```

The env file contains secrets and UI-edited settings. The data directory contains `foxhole.db` and any SQLite sidecar files. If `FOXHOLE_DATABASE_PATH` is overridden, back up that configured database path instead of `/opt/homelab-agent/data/`.

Create a backup on the host:

```bash
sudo systemctl stop homelab-agent
sudo tar -C / -czf ./foxhole-systemd-$(date +%Y%m%d-%H%M%S).tgz etc/homelab-agent/foxhole.env opt/homelab-agent/data
sudo systemctl start homelab-agent
```

Restore to an installed host:

```bash
sudo systemctl stop homelab-agent
sudo tar -C / -xzf ./foxhole-systemd-YYYYMMDD-HHMMSS.tgz
sudo chown -R agent:agent /opt/homelab-agent/data
sudo chown root:agent /etc/homelab-agent/foxhole.env
sudo chmod 0660 /etc/homelab-agent/foxhole.env
sudo systemctl start homelab-agent
```

No secrets are stored in the playbook, inventory, or committed env examples.
