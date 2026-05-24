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
Config directory: /etc/homelab-agent
Env file: /etc/homelab-agent/foxhole.env
```

The env file is created empty and never overwritten by Ansible. Add secrets on the target host after provisioning. Settings changed through the API or dashboard are written back to `/etc/homelab-agent/foxhole.env`.

## Manual Fallback

On Debian 12 or Ubuntu LTS:

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip python3-dev build-essential git curl nmap docker.io
sudo useradd --system --create-home --home-dir /opt/homelab-agent --shell /usr/sbin/nologin agent
sudo install -d -o agent -g agent -m 0750 /opt/homelab-agent
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

No secrets are stored in the playbook, inventory, or committed env examples.
