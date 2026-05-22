# Tautulli and Overseerr Integration

Foxhole reads Tautulli and Overseerr to explain media server failures alongside Plex and *Arr evidence. Both are read-only in this milestone.

## Auth

- **Tautulli** uses `?apikey=` as a query parameter on every `/api/v2` call.
- **Overseerr** uses the `X-Api-Key` header on every `/api/v1/...` call.

```bash
FOXHOLE_TAUTULLI_BASE_URL=http://tautulli.local:8181
FOXHOLE_TAUTULLI_API_KEY=...

FOXHOLE_OVERSEERR_BASE_URL=http://overseerr.local:5055
FOXHOLE_OVERSEERR_API_KEY=...
```

## Tools

- `tautulli_recent_history` — bounded watch history with explicit `length` cap.
- `tautulli_status` — server status and version for staleness checks.
- `overseerr_requests` — paged request list with optional `filter`.
- `overseerr_failed_requests` — cross-checks `status` and `media.status` to surface failed requests, since Overseerr's `filter` parameter has limited values.
- `media_fault_timeline` — merges Tautulli history and Overseerr failed requests into one timeline sorted by timestamp.

## Known limitations

Overseerr's `filter` query parameter does not expose a dedicated "failed" value. Foxhole works around this by reading the recent request page and filtering on `status` / `media.status` codes (3 declined, 4 available, 5 partially-available — the codes typically associated with failed/unfulfilled requests in your deployment). Adjust `_OVERSEERR_FAILURE_STATUSES` in `tools/observability_tool.py` if your install uses different codes.
