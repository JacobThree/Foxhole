# Release and Upgrade Guide

Foxhole release tags publish container images to GHCR:

```text
ghcr.io/jacobthree/foxhole:<tag>
ghcr.io/jacobthree/foxhole:latest
```

Cut releases from `main` with semantic tags such as `v0.1.0`. The release workflow builds the production image, labels it with the tag, pushes the tag, and refreshes `latest`.

## Version 0.1.0 (MVP)

### Staged Rollout Validation Checklist
- [x] **Stage 1 (Read-Only):** Answers "what is broken right now?" correctly for Plex buffering, container loops, and Proxmox storage limits.
- [x] **Stage 2 (Confirmed Writes):** Tested container restart and confirmed they require human intervention in UI/Chat.
- [x] **Stage 3 (Autonomous):** Autonomous rules remain disabled by default.

### Upgrade Instructions

#### Docker Compose
1. Pin or choose the image tag:
   ```bash
   export FOXHOLE_IMAGE_TAG=v0.1.0
   ```
2. Pull the new image:
   ```bash
   docker compose -f iac/compose/docker-compose.yml pull
   ```
3. Restart the stack:
   ```bash
   docker compose -f iac/compose/docker-compose.yml up -d
   ```

For distributed installs, use the distributed Compose file:

```bash
docker compose -f iac/compose/docker-compose.distributed.yml pull
docker compose -f iac/compose/docker-compose.distributed.yml up -d
```

Contributors can test a release candidate locally without GHCR:

```bash
docker build --build-arg VERSION=v0.1.0-rc -t foxhole:local .
FOXHOLE_IMAGE=foxhole FOXHOLE_IMAGE_TAG=local docker compose -f iac/compose/docker-compose.yml up -d
```

#### Proxmox LXC / Debian Systemd
1. Navigate to your source checkout on the host, for example `/opt/homelab-agent/source`.
2. Pull or checkout the release code:
   ```bash
   git pull origin main
   git checkout v0.1.0
   ```
3. Build the static dashboard from that same checkout:
   ```bash
   cd ui
   pnpm install
   pnpm build
   cd ..
   ```
4. Update the Python package in the service virtualenv:
   ```bash
   sudo /opt/homelab-agent/venv/bin/python -m pip install /opt/homelab-agent/source
   ```
5. Update the served dashboard export:
   ```bash
   sudo install -d -o agent -g agent -m 0755 /opt/homelab-agent/ui/out
   sudo cp -a /opt/homelab-agent/source/ui/out/. /opt/homelab-agent/ui/out/
   sudo chown -R agent:agent /opt/homelab-agent/ui
   ```
6. Restart the service:
   ```bash
   sudo systemctl restart homelab-agent
   ```

### Rollback
To rollback Compose, set `FOXHOLE_IMAGE_TAG` to the previous tag and restart. For systemd installs, checkout the previous tag (for example, `git checkout v0.0.9`), rebuild/copy `ui/out`, reinstall the Python package, and restart the service using the steps above.
