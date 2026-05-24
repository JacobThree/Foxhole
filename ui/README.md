# Foxhole UI

The dashboard is a Next.js App Router UI. Production builds are statically exported and served by the FastAPI app from the same origin.

## Development

Run the UI separately when working on frontend code:

```bash
pnpm install
NEXT_PUBLIC_API_URL=http://localhost:8000 pnpm dev
```

Open `http://localhost:3000`.

If `NEXT_PUBLIC_API_URL` is not set, API calls use relative paths such as `/readyz` and `/dashboard/summary`. That is the production shape when FastAPI serves the exported dashboard.

## Static Export

```bash
pnpm build
```

The build writes static assets to `out/`. The backend Docker image copies that directory into `/app/ui/out`. Source-based systemd and LXC installs copy the same directory to `/opt/homelab-agent/ui/out` and set `FOXHOLE_STATIC_UI_DIR` so FastAPI can serve it without Node.js.
