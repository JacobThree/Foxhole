# Docker Compose Deployment

The default Compose stack runs one Foxhole service plus the internal Docker socket proxy. The Foxhole service serves the dashboard, API, in-process scheduler, and SQLite-backed history on `127.0.0.1:8000`. Redis, Celery worker, and Celery beat are available only through the `distributed` profile. Flower is debug-only and is published on `127.0.0.1:5555` only when the `debug` profile is enabled. The Docker socket proxy is on an internal-only network and has no host port.

Durable SQLite state is stored in `iac/compose/data/foxhole.db` on the host and mounted into the runtime as `/app/data/foxhole.db`. Settings changed through the API or dashboard are written to `iac/compose/config/foxhole.env` and mounted as `/config/foxhole.env`. Back up both files before recreating or moving the stack.

The example config sets `FOXHOLE_SESSION_COOKIE_SECURE=false` so browser login works on the default local HTTP URL. Set it to `true` when serving Foxhole behind HTTPS.

## Start

```bash
mkdir -p iac/compose/data iac/compose/config
cp iac/compose/.env.example iac/compose/config/foxhole.env
docker compose -f iac/compose/docker-compose.yml config
docker compose -f iac/compose/docker-compose.yml up --build
```

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

The backend image builds the Next.js static export and serves it from the FastAPI process. A separate Node.js process is only needed for frontend development.

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
docker compose -f iac/compose/docker-compose.yml up --build -d
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

## Distributed Runtime

The distributed profile keeps the older Redis/Celery mode available for advanced installs that want separate API, worker, and beat processes:

```bash
FOXHOLE_RUNTIME_MODE=distributed \
  docker compose -f iac/compose/docker-compose.yml --profile distributed up --build
```

The profile starts Redis, `worker`, and `beat`. Set `FOXHOLE_RUNTIME_MODE=distributed` for the API service when using this profile so scheduled checks run through Celery beat instead of the in-process scheduler.

## Optional Flower Debug UI

Flower is not part of the default runtime. Start it only when debugging Celery:

```bash
docker compose -f iac/compose/docker-compose.yml --profile distributed --profile debug up flower
```

## Stage 1 Socket Proxy

Stage 1 exposes read-only Docker API groups used by diagnostics: containers, events, images, info, networks, and version. It sets `POST=0` and keeps mutation groups such as build, exec, secrets, services, swarm, tasks, and volumes disabled.

The proxy is reachable only by services on the internal `socket-proxy` network:

```text
tcp://docker-socket-proxy:2375
```

## Stage 2 Override

Use `iac/compose/socket-proxy.stage2.yml` only after write tools are protected by Foxhole confirmation tokens:

```bash
docker compose \
  -f iac/compose/docker-compose.yml \
  -f iac/compose/socket-proxy.stage2.yml \
  up --build
```

The override enables `POST` for narrowly scoped container remediations. It still leaves exec, image build, and volume mutation disabled.
