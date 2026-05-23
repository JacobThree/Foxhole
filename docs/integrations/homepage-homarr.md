# Homepage/Homarr Widget

Foxhole exposes a compact JSON endpoint for self-hosted dashboards:

```text
GET /widgets/homepage?token=<FOXHOLE_WIDGET_TOKEN>
```

Enable it explicitly:

```env
FOXHOLE_WIDGET_ENABLED=true
FOXHOLE_WIDGET_TOKEN=change-me
```

The response is intentionally small so Homepage, Homarr, or a custom widget can poll it:

```json
{
  "status": "warning",
  "warning_count": 2,
  "critical_count": 0,
  "latest_incident": null,
  "suggested_action": "Review the latest Foxhole event."
}
```

`status` is `ok`, `warning`, or `critical`. The widget endpoint is disabled by default. When
`FOXHOLE_WIDGET_TOKEN` is configured, callers must pass the token with the `token` query parameter,
`x-foxhole-widget-token` header, or `Authorization: Bearer <token>`.
