# Docker Integration

Foxhole talks to Docker through `tecnativa/docker-socket-proxy`, not a mounted Docker socket. Stage 1 diagnostics use:

- `docker_list_containers` for id, name, image, status, health, labels, ports, and restart count.
- `docker_inspect_container` for the same bounded container metadata on one target.
- `docker_read_logs` for explicit `lines` and `max_bytes` bounded log reads.
- `docker_detect_restart_loops` for containers with high restart counts or restarting/dead state.

Configure the proxy URL with:

```bash
FOXHOLE_DOCKER_ENABLED=true
FOXHOLE_DOCKER_SOCKET_PROXY_URL=tcp://docker-socket-proxy:2375
```

The proxy URL has no default in the application settings. Docker diagnostics are
reported as incomplete until both the integration is enabled and the socket proxy
URL is present.

For Compose installs, start the optional read-only proxy with:

```bash
docker compose -f iac/compose/docker-compose.yml --profile docker up -d
```

The socket proxy should return `403` for blocked endpoints. Foxhole reports those as permission errors instead of crashing.

Stage 2 adds `docker_container_action` for `start`, `stop`, and `restart`. It is confirmation-gated by the shared write policy and does not expose exec, image build, volume mutation, or delete operations.
