# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-05-22

### Added
- **Core Agent**: Pydantic settings, LiteLLM router, tool registry, and write-policy engine.
- **Diagnostic Tools**: Proxmox, Docker, Plex, Sonarr, Radarr, Tautulli, Overseerr, Pi-hole, Unbound, and Nmap tools.
- **Background Workers**: Celery background jobs for periodic checks and Telegram alert dispatcher.
- **Deployment**: Docker Compose skeleton, Proxmox LXC install script, and Ansible Debian/Ubuntu playbook.
- **Web UI**: Next.js control plane with Dashboard, Chat, Alerts, and Settings pages.
- **Docs**: Runbooks for common troubleshooting scenarios.
- **Mock Mode**: Offline fixture mode for testing UI and API without real credentials.
