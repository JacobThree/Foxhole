# Sonarr and Radarr Integration

Foxhole talks to Sonarr and Radarr through their v3 APIs using the `X-Api-Key` header. Each service has its own key — Sonarr and Radarr never share auth.

## Read-only tools

- `arr_queue` — paged download queue with status messages and warnings.
- `arr_health` — health checks reported by the service.
- `arr_root_folders` — configured root folders and free space.
- `arr_download_clients` — configured download clients.
- `arr_quality_profiles` — quality profiles available on the service.
- `arr_import_diagnosis` — compares queue `outputPath` against the configured root folders and surfaces Docker volume path mismatches with the original status messages preserved.

## Configuration

```bash
FOXHOLE_SONARR_BASE_URL=http://sonarr.local:8989
FOXHOLE_SONARR_API_KEY=...

FOXHOLE_RADARR_BASE_URL=http://radarr.local:7878
FOXHOLE_RADARR_API_KEY=...
```

## Why import diagnosis is useful

A common Sonarr/Radarr failure mode is downloading into `/downloads/complete/...` inside the container while the library root inside the same container is `/tv` or `/movies`. The download finishes but the import never runs because the file is outside the visible root. `arr_import_diagnosis` flags every queue item whose `outputPath` is not under any configured root folder.
