# Container Crash Loop Runbook

## Overview
This runbook explains how Foxhole diagnoses Docker containers that are repeatedly crashing or stuck in a restart loop.

## What Foxhole Checks (Read-Only)
When investigating a crash loop, Foxhole performs the following:
1. **Container Status:** Checks the `Status` and `State` fields via the Docker API.
2. **Restart Count:** Looks at the `RestartCount` to quantify the severity of the loop.
3. **Recent Logs:** Fetches the last 50-100 lines of stderr/stdout from the container to identify explicit fatal errors or exceptions.
4. **Healthchecks:** Checks if the container has a failing Docker native healthcheck.

## Manual Actions Required
If the container is missing environment variables, has broken volume mounts, or has corrupt internal data, you must manually fix the configuration in your `docker-compose.yml` or Portainer stack and redeploy.

## Example Prompts
- *"Why is the `radarr` container constantly restarting?"*
- *"Show me the logs for the `foxhole-worker` container, it seems to be crashing."*
- *"Check if any containers are currently in a restart loop."*
