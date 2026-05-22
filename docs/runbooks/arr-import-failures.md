# Runbook: Sonarr/Radarr Import Failures

## What the agent checks

- `arr_queue` — current download queue including warnings and status messages.
- `arr_health` — service-reported health issues such as indexer or download client problems.
- `arr_root_folders` — configured root folders and free space.
- `arr_download_clients` — download client configuration.
- `arr_import_diagnosis` — flags queue items whose `outputPath` lives outside any configured root folder, the most common cause of "downloaded but never imported" symptoms.

## Required permissions

- Service URL and API key for the affected service: `FOXHOLE_SONARR_*` or `FOXHOLE_RADARR_*`.

## Write actions (confirmation-gated, Stage 2 only)

- `arr_update_quality_profile` — rename a profile and toggle `upgradeAllowed`. Returns a before/after diff. Does not perform bulk profile rewrites.
- `arr_queue_item_action` — remove a specific queue item and optionally blocklist the release.

Both actions are denied in Stage 1 and require a confirmation token in Stage 2.

## Example prompts

- "Why is this Sonarr download stuck in the queue?"
- "Did Sonarr import the episode I downloaded last night?"
- "Is the Radarr root folder path actually mounted in the container?"

## Expected evidence

- Queue item id, title, status, and original status messages from the service.
- Output path observed alongside the configured root folder list.
- Health warnings as the service reports them, not paraphrased.
