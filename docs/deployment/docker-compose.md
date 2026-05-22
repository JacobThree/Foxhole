# Docker Compose Deployment

The Compose stack runs the API, Celery worker, Celery beat, Redis, Flower, and a Docker socket proxy. The API is published on `127.0.0.1:8000`; Flower is published on `127.0.0.1:5555`. The Docker socket proxy is on an internal-only network and has no host port.

## Start

```bash
cp iac/compose/.env.example iac/compose/.env
docker compose -f iac/compose/docker-compose.yml config
docker compose -f iac/compose/docker-compose.yml up --build
```

Check process health:

```bash
curl http://127.0.0.1:8000/healthz
```

Readiness is authenticated and also checks Redis:

```bash
curl -H "Authorization: Bearer $FOXHOLE_API_BEARER_TOKEN" http://127.0.0.1:8000/readyz
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

