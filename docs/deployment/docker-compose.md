# Docker Compose Deployment

The default Compose stack runs one Foxhole service from `ghcr.io/jacobthree/foxhole`. The service serves the dashboard, API, in-process scheduler, and SQLite-backed history on `127.0.0.1:8000`. The Docker socket proxy is optional and available through the `docker` profile with read-only defaults. Redis, Celery worker, and Celery beat are available through `iac/compose/docker-compose.distributed.yml`. Flower is debug-only and is published on `127.0.0.1:5555` only when the `debug` profile is enabled.

Durable SQLite state is stored in `iac/compose/data/foxhole.db` on the host and mounted into the runtime as `/app/data/foxhole.db`. Settings changed through the API or dashboard are written to `iac/compose/config/foxhole.env` and mounted as `/config/foxhole.env`. Back up both files before recreating or moving the stack.

The example config sets `FOXHOLE_SESSION_COOKIE_SECURE=false` so browser login works on the default local HTTP URL. Set it to `true` when serving Foxhole behind HTTPS.

## Start

```bash
mkdir -p iac/compose/data iac/compose/config
cp iac/compose/.env.example iac/compose/config/foxhole.env
docker compose -f iac/compose/docker-compose.yml config
docker compose -f iac/compose/docker-compose.yml up -d
```

Edit `iac/compose/config/foxhole.env` before the first start. `FOXHOLE_API_BEARER_TOKEN` is the only required first-run value.

Open the dashboard:

```text
http://127.0.0.1:8000
```

Check process health:

```bash
curl http://127.0.0.1:8000/healthz
```

Readiness is authenticated. In the default `single` runtime it does not require Redis:

```bash
curl -H "Authorization: Bearer $FOXHOLE_API_BEARER_TOKEN" http://127.0.0.1:8000/readyz
```

The backend image includes the Next.js static export and serves it from the FastAPI process. A separate Node.js process is only needed for frontend development.

## Image Tags And Local Builds

By default, Compose pulls:

```text
ghcr.io/jacobthree/foxhole:latest
```

Pin a tagged release by setting `FOXHOLE_IMAGE_TAG`:

```bash
FOXHOLE_IMAGE_TAG=v0.1.0 docker compose -f iac/compose/docker-compose.yml pull
FOXHOLE_IMAGE_TAG=v0.1.0 docker compose -f iac/compose/docker-compose.yml up -d
```

Contributors can build locally and run the same Compose file against that local image:

```bash
docker build -t foxhole:local .
FOXHOLE_IMAGE=foxhole FOXHOLE_IMAGE_TAG=local docker compose -f iac/compose/docker-compose.yml up -d
```

## Backup And Restore

Back up these host paths:

```text
iac/compose/data/
iac/compose/config/
```

`data/` contains the SQLite database and possible SQLite sidecar files. `config/foxhole.env` contains the bearer token, integration secrets, cookie settings, and any settings changed through the dashboard or API.

Create a backup from the repository root:

```bash
docker compose -f iac/compose/docker-compose.yml stop
mkdir -p backups
tar -C iac/compose -czf backups/foxhole-compose-$(date +%Y%m%d-%H%M%S).tgz data config
docker compose -f iac/compose/docker-compose.yml up -d
```

Restore onto a fresh or stopped Compose deployment:

```bash
docker compose -f iac/compose/docker-compose.yml down
mkdir -p iac/compose
tar -C iac/compose -xzf backups/foxhole-compose-YYYYMMDD-HHMMSS.tgz
docker compose -f iac/compose/docker-compose.yml up -d
```

If `FOXHOLE_DATABASE_PATH` is changed from `/app/data/foxhole.db`, back up the host mount that contains the configured path instead of only `iac/compose/data/`.

## Reverse Proxy

Keep the Compose port bound to localhost and proxy only the unified Foxhole app:

```text
127.0.0.1:8000 -> Foxhole dashboard/API
```

Caddy example:

```caddyfile
foxhole.example.com {
	reverse_proxy 127.0.0.1:8000
}
```

Use these settings when the public URL is HTTPS:

```env
FOXHOLE_SESSION_COOKIE_SECURE=true
FOXHOLE_SESSION_COOKIE_SAMESITE=lax
```

Do not proxy or publish `docker-socket-proxy`, Redis, Celery worker, or Celery beat. They are internal runtime services, not browser endpoints.

If you intentionally run a separate UI origin instead of the same-origin dashboard served by Foxhole, allow that UI origin explicitly and use secure cross-site cookies:

```env
FOXHOLE_UI_ALLOWED_ORIGINS=["https://dashboard.example.com"]
FOXHOLE_SESSION_COOKIE_SECURE=true
FOXHOLE_SESSION_COOKIE_SAMESITE=none
```

## Optional Docker Diagnostics

The socket proxy is disabled by default. Enable it only when Docker diagnostics are configured:

```bash
docker compose -f iac/compose/docker-compose.yml --profile docker up -d
```

When enabling Docker diagnostics in `config/foxhole.env`, keep the proxy URL pointed at the internal service:

```env
FOXHOLE_DOCKER_ENABLED=true
FOXHOLE_DOCKER_SOCKET_PROXY_URL=tcp://docker-socket-proxy:2375
```

Stage 1 exposes read-only Docker API groups used by diagnostics: containers, events, images, info, networks, and version. It sets `POST=0` and keeps mutation groups such as build, exec, secrets, services, swarm, tasks, and volumes disabled. The proxy is reachable only by services on the internal `socket-proxy` network.

## Distributed Runtime

The distributed Compose file keeps the older Redis/Celery mode available for advanced installs that want separate API, worker, and beat processes:

```bash
docker compose -f iac/compose/docker-compose.distributed.yml up -d
```

The file starts Redis, `worker`, and `beat`, and sets `FOXHOLE_RUNTIME_MODE=distributed` for the Foxhole service so scheduled checks run through Celery beat instead of the in-process scheduler.

## Optional Flower Debug UI

Flower is not part of the default runtime. Start it only when debugging Celery:

```bash
docker compose -f iac/compose/docker-compose.distributed.yml --profile debug up flower
```

## Stage 2 Override

Use `iac/compose/socket-proxy.stage2.yml` only after write tools are protected by Foxhole confirmation tokens:

```bash
docker compose \
  -f iac/compose/docker-compose.yml \
  -f iac/compose/socket-proxy.stage2.yml \
  --profile docker \
  up -d
```

The override enables `POST` for narrowly scoped container remediations. It still leaves exec, image build, and volume mutation disabled.
