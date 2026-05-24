# Docker Compose Deployment

The Compose stack runs the Foxhole dashboard, API, Celery worker, Celery beat, Redis, and a Docker socket proxy by default. The dashboard and API are published together on `127.0.0.1:8000`. Flower is debug-only and is published on `127.0.0.1:5555` only when the `debug` profile is enabled. The Docker socket proxy is on an internal-only network and has no host port.

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

Readiness is authenticated and also checks Redis:

```bash
curl -H "Authorization: Bearer $FOXHOLE_API_BEARER_TOKEN" http://127.0.0.1:8000/readyz
```

The backend image builds the Next.js static export and serves it from the FastAPI process. A separate Node.js process is only needed for frontend development.

## Optional Flower Debug UI

Flower is not part of the default runtime. Start it only when debugging Celery:

```bash
docker compose -f iac/compose/docker-compose.yml --profile debug up flower
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
