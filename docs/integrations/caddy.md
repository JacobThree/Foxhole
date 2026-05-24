# Caddy

## Serving Foxhole Behind Caddy

Foxhole's default runtime serves the dashboard and API from the same process, so Caddy should proxy only the user-facing Foxhole port:

```caddyfile
foxhole.example.com {
	reverse_proxy 127.0.0.1:8000
}
```

Set browser-cookie options for HTTPS:

```env
FOXHOLE_SESSION_COOKIE_SECURE=true
FOXHOLE_SESSION_COOKIE_SAMESITE=lax
```

The proxy target should be the unified Foxhole app. Do not expose the Docker socket proxy, Redis, Celery worker, Celery beat, or Flower through Caddy.

If the dashboard and API are intentionally split across different origins, keep HTTPS enabled and allow the UI origin explicitly:

```env
FOXHOLE_UI_ALLOWED_ORIGINS=["https://dashboard.example.com"]
FOXHOLE_SESSION_COOKIE_SECURE=true
FOXHOLE_SESSION_COOKIE_SAMESITE=none
```

With the unified app, Caddy routes `/`, `/healthz`, and API endpoints such as `/readyz`, `/capabilities`, and `/dashboard/summary` to the same upstream.

## Caddy Diagnostic Integration

Foxhole's Caddy integration is read-only. It can read either a mounted Caddyfile or the local
Caddy admin API, list reverse-proxy routes, and flag upstream targets that look likely to cause
502s.

```env
FOXHOLE_CADDY_ENABLED=true
FOXHOLE_CADDY_CONFIG_PATH=/etc/caddy/Caddyfile
# or:
FOXHOLE_CADDY_ADMIN_API_URL=http://localhost:2019
```

Capabilities exposed through the integration manifest:

- `reverse_proxy.routes.read`
- `reverse_proxy.upstreams.read`
- `reverse_proxy.routes.diagnose`

The integration does not edit Caddy configuration. It reports route/upstream evidence so Foxhole
can correlate failed monitors, missing Docker containers, and likely reverse-proxy routing issues.
