# Caddy

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
