# Runbook: Plex Buffering

## What the agent checks

- Active sessions, per-stream decision, and total bandwidth (`plex_active_sessions`).
- Transcode counts and whether the Plex host is using hardware transcoding (`plex_transcode_status`).
- Buffering risk score with concrete checks to run next (`plex_buffering_diagnosis`).
- Bounded Plex log analysis for database locks, slow SQL, and transcoder errors (`plex_analyze_logs`).
- Manual debug logging guidance (`plex_debug_guidance`). Foxhole never toggles Plex settings.

## Required permissions

- `FOXHOLE_PLEX_BASE_URL` and `FOXHOLE_PLEX_TOKEN`.
- Read access to the Plex Media Server log file if log analysis is desired.

## Manual actions that remain with the operator

- Enabling or disabling verbose logging in Plex Settings.
- Restarting Plex Media Server.
- Adjusting hardware transcoding settings or remote bandwidth caps.

## Example prompts

- "Why are users buffering on Plex right now?"
- "Is Plex hardware transcoding actually being used?"
- "Are there database locks in the Plex log from the last hour?"

## Expected evidence in the answer

- Observed session count and decisions.
- Hardware vs software transcode breakdown.
- Specific log lines that matched a known failure category, not paraphrased summaries.
- Clear "data unavailable" when integration or log path is missing.
