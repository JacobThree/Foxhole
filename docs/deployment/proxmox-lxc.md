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
- Creates `/opt/homelab-agent` and `/etc/homelab-agent`.
- Creates an unprivileged `agent` service user.
- Installs `homelab-agent.service` with systemd hardening.
- Reads runtime configuration from `/etc/homelab-agent/foxhole.env`.

Set `FOXHOLE_REPO_URL` when running the installer if the source is not copied into `/tmp/foxhole-src`:

```bash
sudo FOXHOLE_REPO_URL=https://github.com/<owner>/<repo>.git iac/lxc/install-homelab-agent.sh
```

After the container is created, fill `/etc/homelab-agent/foxhole.env` inside the container and start the service:

```bash
pct exec 240 -- editor /etc/homelab-agent/foxhole.env
pct exec 240 -- systemctl start homelab-agent
```

The bootstrap does not require privileged container mode by default. Keep `UNPRIVILEGED=1` unless a future diagnostic tool has a specific, documented need.

