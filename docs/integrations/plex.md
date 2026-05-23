# Plex Integration

Foxhole queries Plex through the HTTP API using `X-Plex-Token`. Tools are read-only and never toggle Plex settings.

- `plex_active_sessions` — user, title, player, decision, hardware transcode, bandwidth per active stream.
- `plex_transcode_status` — counts of direct play, direct stream, hardware transcode, and software transcode, plus total bandwidth.
- `plex_analyze_logs` — bounded read of `Plex Media Server.log`. Detects `database is locked`, `SQLITE_BUSY`, slow SQL, and transcoder errors.
- `plex_buffering_diagnosis` — combines session and transcode signals into a `low`/`elevated`/`high` risk read with explicit checks to run next.

Configure with:

```bash
FOXHOLE_PLEX_BASE_URL=http://plex.local:32400
FOXHOLE_PLEX_TOKEN=...
FOXHOLE_PLEX_LOG_PATH="/var/lib/plexmediaserver/Library/Application Support/Plex Media Server/Logs/Plex Media Server.log"
```

For native Plex installs on Proxmox LXC, the log file usually lives at:

```
/var/lib/plexmediaserver/Library/Application Support/Plex Media Server/Logs/Plex Media Server.log
```

If the path is missing, `plex_analyze_logs` returns a clear "log path is not available" error instead of crashing.

Foxhole never enables or disables Plex debug logging automatically. Use `plex_debug_guidance` (Task 21) for the manual workflow.
