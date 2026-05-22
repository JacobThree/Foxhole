# HomelabGPT: Production Technical Specification for an Open-Source AI Agent for Homelab Management

**TL;DR**
- A Python/FastAPI agent using **LiteLLM** as the provider-agnostic LLM layer, **Pydantic v2 + Instructor** for strict tool I/O, **Celery 5 / Redis 7** for background work, and a hardened **`tecnativa/docker-socket-proxy`** for blast-radius reduction is the recommended architecture.
- Deploy as a Docker Compose v3.9 stack on a dedicated unprivileged Debian 12 Proxmox LXC (community-scripts/ProxmoxVE bootstrap pattern), with a restricted PVE API token (audit-only roles + `VM.Migrate`) and read-only API keys for Plex / Sonarr / Radarr / Tautulli / Overseerr / Pi-hole.
- Build the agent as five concrete tool families (`docker`, `proxmox`, `plex`, `arr`, `networking`), surface them via Pydantic-typed function calls with a 3-attempt JSON correction loop, schedule recurring checks via Celery beat, and push MarkdownV2 alerts to Telegram.

---

## Key Findings

1. **LiteLLM is the right abstraction layer.** Its `Router` supports per-deployment `rpm`/`tpm`, `model_name` aliases, `fallbacks`, and runtime override of `api_base`/`api_key`/`model` — letting a single agent target OpenAI, Anthropic, vLLM, or local Ollama interchangeably via one `completion()` call.
2. **Instructor + Pydantic v2 is the cheapest way to get reliable tool I/O from local LLMs.** It auto-retries on `ValidationError` by feeding the error message back to the model — perfect for the failure-prone JSON output of `ollama_chat/qwen2.5:7b`-class models.
3. **`tecnativa/docker-socket-proxy` (HAProxy-based) is the canonical hardening pattern.** Set `CONTAINERS=1 SERVICES=1 TASKS=1 INFO=1 POST=1 ALLOW_START=1 ALLOW_STOP=1 ALLOW_RESTARTS=1` while leaving `BUILD=0 IMAGES=0 EXEC=0 VOLUMES=0 SECRETS=0 AUTH=0`. The agent then sets `DOCKER_HOST=tcp://socket-proxy:2375`.
4. **Proxmox API tokens must have `--privsep=0` OR be granted explicit ACLs** — `privsep=1` tokens get an empty permission set by default and silently 401. The right pattern is a dedicated `homelab-agent@pve` user with a custom `HomelabAgent` role limited to `VM.Audit`, `Datastore.Audit`, `Sys.Audit`, `SDN.Audit`, `VM.Migrate`.
5. **The community-scripts/ProxmoxVE project (formerly tteck/Proxmox) is the standard LXC bootstrap pattern.** Scripts source `https://raw.githubusercontent.com/community-scripts/ProxmoxVE/main/misc/build.func` and expose `var_cpu`, `var_ram`, `var_disk`, `var_os`, `var_version`, `var_unprivileged`, `var_tags`.
6. **Pi-hole's `/admin/api.php` requires `?auth=<token>` for `recentBlocked` and `getAllQueries`.** Per the official Pi-hole blog post "Upcoming changes: authentication for more API endpoints required" (November 17, 2022): *"Most endpoints already require a token for authentication. However, not all endpoints required a token so far. In the near future, the endpoints status, summary, summaryRaw and overTimeData10mins will also require a token."*
7. **`python-telegram-bot` v20+ is fully asyncio-native.** Per official docs (python-telegram-bot.org), v20.x supports Python 3.8+, but the current latest release on PyPI (v22.7) requires Python 3.10+. All `bot.send_message(...)` calls must be `await`-ed; `ParseMode.MARKDOWN_V2` requires escaping every `_ * [ ] ( ) ~ \` > # + - = | { } . !` (use `telegram.helpers.escape_markdown(text, version=2)`).
8. **Tautulli, Overseerr, and Sonarr/Radarr APIs all use distinct auth schemes**: Tautulli (`?apikey=` query param), Overseerr (`X-Api-Key` header), *Arr v3 (`X-Api-Key` header).

---

## Details

### 1. Core Architecture & LLM Abstraction

#### 1.1 Provider-Agnostic Engine (LiteLLM Router)

The agent uses LiteLLM's `Router` as the single chokepoint for all LLM traffic. Provider keys are loaded at runtime from `/etc/homelab-agent/providers.yaml` and bound to model aliases.

**`agent/llm/router_config.yaml`:**

```yaml
model_list:
  - model_name: agent-primary
    litellm_params:
      model: anthropic/claude-sonnet-4-5-20250929
      api_key: os.environ/ANTHROPIC_API_KEY
      rpm: 50
      tpm: 200000

  - model_name: agent-primary
    litellm_params:
      model: openai/gpt-4o-2024-11-20
      api_key: os.environ/OPENAI_API_KEY
      rpm: 60
      tpm: 250000

  - model_name: agent-local
    litellm_params:
      model: ollama_chat/qwen2.5:14b-instruct
      api_base: http://ollama.lan:11434
      keep_alive: "10m"
      rpm: 30
    model_info:
      supports_function_calling: true

  - model_name: agent-vllm
    litellm_params:
      model: openai/meta-llama/Meta-Llama-3.1-8B-Instruct
      api_base: http://vllm.lan:8000/v1
      api_key: sk-vllm-internal
      rpm: 120

router_settings:
  routing_strategy: simple-shuffle
  enable_pre_call_checks: true
  num_retries: 2
  request_timeout: 60
  redis_host: os.environ/REDIS_HOST
  redis_port: 6379
  fallbacks:
    - agent-primary: [agent-vllm, agent-local]
    - agent-local:   [agent-vllm]
  retry_policy:
    AuthenticationErrorRetries: 0
    TimeoutErrorRetries: 3
    RateLimitErrorRetries: 3
    InternalServerErrorRetries: 2
  allowed_fails_policy:
    AuthenticationErrorAllowedFails: 1
    RateLimitErrorAllowedFails: 100
    TimeoutErrorAllowedFails: 12
```

**`agent/llm/client.py`:**

```python
from __future__ import annotations
import yaml
from litellm import Router

class LLMClient:
    def __init__(self, config_path: str = "/etc/homelab-agent/router_config.yaml"):
        with open(config_path) as f:
            cfg = yaml.safe_load(f)
        self.router = Router(model_list=cfg["model_list"], **cfg["router_settings"])

    async def chat(self, messages, model="agent-primary", tools=None,
                   api_base=None, api_key=None, override_model=None, **kwargs):
        call_kwargs = {"model": model, "messages": messages, "tools": tools, **kwargs}
        if api_base:       call_kwargs["api_base"] = api_base
        if api_key:        call_kwargs["api_key"]  = api_key
        if override_model: call_kwargs["model"]    = override_model
        return await self.router.acompletion(**call_kwargs)
```

#### 1.2 Strict Tool Execution with Pydantic v2 + Instructor

All tools declare their input as a Pydantic v2 `BaseModel`, exported via `.model_json_schema()`. A 3-attempt correction loop wraps every tool dispatch.

**`agent/tools/base.py`:**

```python
from __future__ import annotations
import json, re, logging
from typing import Type
from pydantic import BaseModel, ValidationError
from litellm import acompletion

log = logging.getLogger(__name__)

class ToolSpec(BaseModel):
    name: str
    description: str
    args_model: Type[BaseModel]

    def openai_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.args_model.model_json_schema(),
            },
        }

JSON_OBJ_RE = re.compile(r"\{(?:[^{}]|(?:\{[^{}]*\}))*\}", re.DOTALL)

async def parse_tool_args(raw: str, schema: Type[BaseModel],
                          correction_model: str = "agent-local",
                          max_attempts: int = 3) -> BaseModel:
    """Try strict json.loads → Pydantic. On failure, ask the LLM to fix.
       Final fallback: regex-extract the first balanced { ... }."""
    last_err = None
    candidate = raw

    for attempt in range(max_attempts):
        try:
            return schema.model_validate_json(candidate)
        except (ValidationError, json.JSONDecodeError) as e:
            last_err = e
            log.warning("tool-args parse attempt %d failed: %s", attempt + 1, e)
            if attempt == max_attempts - 1:
                break
            fix_prompt = (
                f"The following JSON failed validation against this schema:\n"
                f"```json\n{json.dumps(schema.model_json_schema(), indent=2)}\n```\n"
                f"Error: {e}\n\nMalformed output:\n```\n{candidate}\n```\n"
                f"Return ONLY corrected JSON. No prose, no markdown fences."
            )
            resp = await acompletion(
                model=correction_model,
                messages=[{"role": "user", "content": fix_prompt}],
                temperature=0.0,
                response_format={"type": "json_object"},
            )
            candidate = resp.choices[0].message.content

    m = JSON_OBJ_RE.search(raw)
    if m:
        try:
            return schema.model_validate_json(m.group(0))
        except ValidationError:
            pass
    raise RuntimeError(f"tool-args correction exhausted: {last_err}") from last_err
```

**Example concrete tool:**

```python
from pydantic import BaseModel, Field
from typing import Literal
from .base import ToolSpec

class ContainerAction(BaseModel):
    container: str = Field(..., description="Container name or 12-char ID")
    action: Literal["start", "stop", "restart"]
    timeout_s: int = Field(10, ge=1, le=120)

container_action_tool = ToolSpec(
    name="container_action",
    description="Start, stop, or restart a Docker container by name.",
    args_model=ContainerAction,
)
```

#### 1.3 Deployment Blueprints

##### 1.3.1 Docker Compose v3.9 stack

**`iac/compose/docker-compose.yml`:**

```yaml
version: "3.9"

x-restart: &default-restart
  restart: unless-stopped

networks:
  agent-net:
    driver: bridge
    ipam: { config: [{ subnet: 172.30.40.0/24 }] }
  socket-proxy-net:
    driver: bridge
    internal: true

volumes:
  redis-data:
  agent-cache:

services:

  socket-proxy:
    image: tecnativa/docker-socket-proxy:0.3.0
    container_name: hl-socket-proxy
    <<: *default-restart
    privileged: true
    networks: [socket-proxy-net]
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    environment:
      LOG_LEVEL: info
      CONTAINERS: 1
      SERVICES:   1
      TASKS:      1
      INFO:       1
      NETWORKS:   1
      VERSION:    1
      EVENTS:     1
      PING:       1
      POST:       1
      ALLOW_START:    1
      ALLOW_STOP:     1
      ALLOW_RESTARTS: 1
      BUILD:    0
      COMMIT:   0
      EXEC:     0
      IMAGES:   0
      VOLUMES:  0
      SECRETS:  0
      CONFIGS:  0
      AUTH:     0
      SWARM:    0
      NODES:    0
      SESSION:  0
      SYSTEM:   0
      DISTRIBUTION: 0
    read_only: true
    tmpfs: [/run]
    security_opt: [no-new-privileges:true]
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://localhost:2375/_ping"]
      interval: 30s
      timeout: 5s
      retries: 3

  redis:
    image: redis:7.4-alpine
    container_name: hl-redis
    <<: *default-restart
    networks: [agent-net]
    command: ["redis-server", "--save", "60", "1", "--appendonly", "yes",
              "--maxmemory", "512mb", "--maxmemory-policy", "allkeys-lru"]
    volumes: [redis-data:/data]
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 15s
      timeout: 3s
      retries: 5

  agent:
    image: ghcr.io/yourorg/homelab-agent:1.0.0
    container_name: hl-agent
    <<: *default-restart
    depends_on:
      redis:        { condition: service_healthy }
      socket-proxy: { condition: service_healthy }
    networks: [agent-net, socket-proxy-net]
    ports: ["127.0.0.1:8800:8800"]
    environment:
      DOCKER_HOST: tcp://socket-proxy:2375
      REDIS_HOST: redis
      REDIS_PORT: 6379
      CELERY_BROKER_URL: redis://redis:6379/0
      CELERY_RESULT_BACKEND: redis://redis:6379/1
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY:-}
      OPENAI_API_KEY:    ${OPENAI_API_KEY:-}
      OLLAMA_API_BASE:   ${OLLAMA_API_BASE:-http://host.docker.internal:11434}
      PVE_HOST:          ${PVE_HOST}
      PVE_TOKEN_ID:      ${PVE_TOKEN_ID}
      PVE_TOKEN_SECRET:  ${PVE_TOKEN_SECRET}
      TELEGRAM_BOT_TOKEN: ${TELEGRAM_BOT_TOKEN}
      TELEGRAM_CHAT_ID:   ${TELEGRAM_CHAT_ID}
      PLEX_TOKEN:        ${PLEX_TOKEN}
      SONARR_API_KEY:    ${SONARR_API_KEY}
      RADARR_API_KEY:    ${RADARR_API_KEY}
      TAUTULLI_API_KEY:  ${TAUTULLI_API_KEY}
      OVERSEERR_API_KEY: ${OVERSEERR_API_KEY}
      PIHOLE_AUTH:       ${PIHOLE_AUTH}
    volumes:
      - agent-cache:/var/cache/agent
      - ./config:/etc/homelab-agent:ro
    security_opt: [no-new-privileges:true]
    cap_drop: [ALL]
    cap_add: [NET_RAW, NET_ADMIN]
    healthcheck:
      test: ["CMD", "curl", "-fsS", "http://localhost:8800/healthz"]
      interval: 30s
      timeout: 5s
      retries: 3

  worker:
    image: ghcr.io/yourorg/homelab-agent:1.0.0
    container_name: hl-worker
    <<: *default-restart
    depends_on: [redis, socket-proxy]
    networks: [agent-net, socket-proxy-net]
    command: ["celery", "-A", "workers.app", "worker", "-Q", "default,scans",
              "-l", "info", "--hostname=worker-1@%h", "--concurrency=4"]
    environment:
      DOCKER_HOST: tcp://socket-proxy:2375
      CELERY_BROKER_URL: redis://redis:6379/0
      CELERY_RESULT_BACKEND: redis://redis:6379/1
    cap_drop: [ALL]
    cap_add: [NET_RAW, NET_ADMIN]
    healthcheck:
      test: ["CMD", "celery", "-A", "workers.app", "inspect", "ping", "-d", "worker-1@%h"]
      interval: 30s
      timeout: 10s
      retries: 3

  beat:
    image: ghcr.io/yourorg/homelab-agent:1.0.0
    container_name: hl-beat
    <<: *default-restart
    depends_on: [redis]
    networks: [agent-net]
    command: ["celery", "-A", "workers.app", "beat", "-l", "info",
              "--schedule=/tmp/celerybeat-schedule"]

  flower:
    image: mher/flower:2.0
    container_name: hl-flower
    <<: *default-restart
    depends_on: [redis]
    networks: [agent-net]
    command: ["celery", "--broker=redis://redis:6379/0", "flower",
              "--port=5555", "--basic_auth=${FLOWER_USER}:${FLOWER_PASS}",
              "--persistent=True"]
    ports: ["127.0.0.1:5555:5555"]
```

##### 1.3.2 Proxmox LXC bootstrap (community-scripts / tteck-style)

**`iac/lxc/install-homelab-agent.sh`** (run on the PVE host as root):

```bash
#!/usr/bin/env bash
source <(curl -fsSL https://raw.githubusercontent.com/community-scripts/ProxmoxVE/main/misc/build.func)
# Copyright (c) 2024 yourorg
# License: MIT
# Source: https://github.com/yourorg/homelab-agent

APP="HomelabAgent"
var_tags="${var_tags:-ai;automation}"
var_cpu="${var_cpu:-2}"
var_ram="${var_ram:-4096}"
var_disk="${var_disk:-12}"
var_os="${var_os:-debian}"
var_version="${var_version:-12}"
var_unprivileged="${var_unprivileged:-1}"

header_info "$APP"
variables
color
catch_errors

function update_script() {
  header_info
  check_container_storage
  check_container_resources
  if [[ ! -d /opt/homelab-agent ]]; then
    msg_error "No ${APP} Installation Found!"; exit
  fi
  msg_info "Updating $APP"
  cd /opt/homelab-agent
  $STD git pull
  $STD /opt/homelab-agent/.venv/bin/pip install -r requirements.txt
  $STD systemctl restart homelab-agent
  msg_ok "Updated $APP"
  exit
}

start
build_container
description

msg_ok "Completed Successfully!\n"
```

The `build_container` function (from `build.func`) ultimately invokes `pct create` along these lines:

```bash
pveam update
pveam download local debian-12-standard_12.7-1_amd64.tar.zst

pct create 200 \
  local:vztmpl/debian-12-standard_12.7-1_amd64.tar.zst \
  --hostname homelab-agent \
  --ostype debian \
  --cores 2 --memory 4096 --swap 512 \
  --rootfs local-lvm:12 \
  --net0 name=eth0,bridge=vmbr0,ip=dhcp,firewall=1 \
  --unprivileged 1 \
  --features nesting=1,keyctl=1 \
  --password 'ChangeMe!' \
  --onboot 1 --start 1 \
  --tags "ai;automation"
```

**`iac/lxc/install/homelab-agent-install.sh`** (runs inside the CT):

```bash
#!/usr/bin/env bash
set -euo pipefail
apt-get update
apt-get install -y --no-install-recommends \
  python3.11 python3.11-venv python3-pip git curl jq nmap ca-certificates

useradd --system --create-home --shell /usr/sbin/nologin agent
install -d -o agent -g agent /opt/homelab-agent /var/log/homelab-agent /etc/homelab-agent

su - agent -s /bin/bash -c '
  git clone https://github.com/yourorg/homelab-agent.git /opt/homelab-agent
  cd /opt/homelab-agent
  python3.11 -m venv .venv
  .venv/bin/pip install --upgrade pip
  .venv/bin/pip install -r requirements.txt
'
```

**`iac/lxc/systemd/homelab-agent.service`:**

```ini
[Unit]
Description=Homelab Agent (FastAPI + LiteLLM)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=agent
Group=agent
EnvironmentFile=/etc/homelab-agent/agent.env
WorkingDirectory=/opt/homelab-agent
ExecStart=/opt/homelab-agent/.venv/bin/uvicorn agent.main:app --host 0.0.0.0 --port 8800 --workers 2
Restart=on-failure
RestartSec=5s
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
ReadWritePaths=/var/log/homelab-agent /var/cache/agent
AmbientCapabilities=CAP_NET_RAW CAP_NET_ADMIN

[Install]
WantedBy=multi-user.target
```

---

### 2. Infrastructure & Security Orchestration

#### 2.1 Docker Socket Proxy

The `socket-proxy` block above (1.3.1) is the complete config. Integration in the agent:

```python
# agent/tools/docker_tool.py
import docker

DOCKER_HOST = "tcp://socket-proxy:2375"
client = docker.DockerClient(base_url=DOCKER_HOST, version="1.43", timeout=15)

def list_containers() -> list[dict]:
    return [
        {"id": c.short_id, "name": c.name, "status": c.status,
         "image": c.image.tags[0] if c.image.tags else c.image.short_id,
         "labels": c.labels}
        for c in client.containers.list(all=True)
    ]

def restart_container(name: str, timeout: int = 10) -> dict:
    c = client.containers.get(name)
    c.restart(timeout=timeout)
    return {"name": c.name, "status": c.status, "restarted": True}
```

A `DELETE /containers/{id}` or `POST /build` from this client returns HTTP 403 because `BUILD=0` and the proxy's HAProxy ruleset blocks container DELETE.

#### 2.2 Portainer Integration

**`agent/tools/portainer_tool.py`:**

```python
import os, time, httpx
from typing import Any

_TOKEN: dict[str, Any] = {"jwt": None, "exp": 0.0}

PORTAINER_URL = os.environ["PORTAINER_URL"].rstrip("/")
PORTAINER_USER = os.environ["PORTAINER_USER"]
PORTAINER_PASS = os.environ["PORTAINER_PASS"]

async def _get_jwt(client: httpx.AsyncClient) -> str:
    # Portainer JWTs are valid for 8 hours; refresh at 7h.
    if _TOKEN["jwt"] and time.time() < _TOKEN["exp"]:
        return _TOKEN["jwt"]
    r = await client.post(
        f"{PORTAINER_URL}/api/auth",
        json={"username": PORTAINER_USER, "password": PORTAINER_PASS},
        timeout=10,
    )
    r.raise_for_status()
    jwt = r.json()["jwt"]
    _TOKEN.update(jwt=jwt, exp=time.time() + 7 * 3600)
    return jwt

async def _auth_headers(client: httpx.AsyncClient) -> dict:
    return {"Authorization": f"Bearer {await _get_jwt(client)}"}

async def list_endpoints() -> list[dict]:
    async with httpx.AsyncClient(verify=False) as c:
        r = await c.get(f"{PORTAINER_URL}/api/endpoints", headers=await _auth_headers(c))
        r.raise_for_status()
        return r.json()

async def list_stacks(endpoint_id: int) -> list[dict]:
    async with httpx.AsyncClient(verify=False) as c:
        r = await c.get(f"{PORTAINER_URL}/api/endpoints/{endpoint_id}/stacks",
                        headers=await _auth_headers(c))
        r.raise_for_status()
        return r.json()

async def git_redeploy_stack(stack_id: int, endpoint_id: int, pull_image: bool = True) -> dict:
    async with httpx.AsyncClient(verify=False, timeout=120) as c:
        r = await c.put(
            f"{PORTAINER_URL}/api/stacks/{stack_id}/git/redeploy",
            params={"endpointId": endpoint_id},
            headers=await _auth_headers(c),
            json={"pullImage": pull_image, "prune": True},
        )
        r.raise_for_status()
        return r.json()
```

For production, prefer Portainer **API access tokens** (`X-API-Key: ptr_...`) over username/password since they don't expire and can be revoked individually.

#### 2.3 Proxmox VE API

**Token creation (PVE host, as root):**

```bash
# 1. Dedicated user
pveum user add homelab-agent@pve --comment "HomelabGPT API user"

# 2. Custom role: audit + safe LXC migration; NO power, NO allocate
pveum role add HomelabAgent --privs \
  "VM.Audit,VM.Migrate,Datastore.Audit,Sys.Audit,SDN.Audit,Pool.Audit"

# 3. Grant role at root path (propagates)
pveum aclmod / --user homelab-agent@pve --role HomelabAgent

# 4. Token with privsep DISABLED so it inherits user perms
pveum user token add homelab-agent@pve agent --privsep 0
# => Token ID: homelab-agent@pve!agent   Secret: 12345678-abcd-...
```

The omission of `Sys.PowerMgmt`, `VM.Allocate`, `Permissions.Modify`, and `Datastore.Allocate` means the token cannot reboot/shutdown nodes, create or destroy VMs, modify ACLs, or allocate storage.

**`agent/tools/proxmox_tool.py`:**

```python
import os
from proxmoxer import ProxmoxAPI

pve = ProxmoxAPI(
    os.environ["PVE_HOST"],
    user="homelab-agent@pve",
    token_name="agent",
    token_value=os.environ["PVE_TOKEN_SECRET"],
    verify_ssl=False,
    timeout=15,
)

def storage_usage(node: str) -> list[dict]:
    return [
        {"id": s["storage"], "type": s["type"],
         "used_pct": round(100 * s["used"] / s["total"], 1) if s.get("total") else None,
         "used_gb": round(s.get("used", 0) / 1e9, 1),
         "total_gb": round(s.get("total", 0) / 1e9, 1)}
        for s in pve.nodes(node).storage.get()
    ]

def lxc_status(node: str) -> list[dict]:
    return [
        {"vmid": c["vmid"], "name": c["name"], "status": c["status"],
         "cpu": c.get("cpu"), "mem_gb": round(c.get("mem", 0) / 1e9, 2),
         "uptime_s": c.get("uptime", 0)}
        for c in pve.nodes(node).lxc.get()
    ]

def migrate_lxc(node: str, vmid: int, target: str, restart: bool = True) -> dict:
    upid = pve.nodes(node).lxc(vmid).migrate.post(target=target, restart=int(restart))
    return {"upid": upid, "vmid": vmid, "from": node, "to": target}
```

Equivalent `pvesh` CLI wrappers:

```bash
pvesh get /nodes/{node}/storage   --output-format=json
pvesh get /nodes/{node}/lxc       --output-format=json
pvesh create /nodes/{node}/lxc/{vmid}/migrate --target {target} --restart 1
```

---

### 3. Application Diagnostics & Log Parsing

#### 3.1 Plex (Native LXC)

**`tools/plex_tool.py`:**

```python
import os, re, subprocess, httpx
from pathlib import Path

PLEX_LOG = Path("/var/lib/plexmediaserver/Library/Application Support/Plex Media Server/Logs/Plex Media Server.log")
PLEX_URL = os.environ.get("PLEX_URL", "http://localhost:32400")
PLEX_TOKEN = os.environ["PLEX_TOKEN"]

SQLITE_PATTERNS = [
    re.compile(r"SQLITE_BUSY"),
    re.compile(r"database is locked", re.I),
    re.compile(r"Slow SQL query .*? took (\d+)ms"),
]

async def diagnose_plex(tail_lines: int = 5000) -> dict:
    diag: dict = {"sessions": [], "hwaccel": False, "db_warnings": []}

    # 1. Active sessions
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(
            f"{PLEX_URL}/status/sessions",
            params={"X-Plex-Token": PLEX_TOKEN},
            headers={"Accept": "application/json"},
        )
        r.raise_for_status()
        for v in (r.json().get("MediaContainer", {}).get("Metadata") or []):
            ts = (v.get("TranscodeSession") or [{}])[0]
            diag["sessions"].append({
                "user":          v.get("User", {}).get("title"),
                "title":         v.get("title"),
                "player":        v.get("Player", {}).get("product"),
                "video_decision": ts.get("videoDecision", "directplay"),
                "audio_decision": ts.get("audioDecision", "directplay"),
                "hw_requested":   ts.get("transcodeHwRequested", False),
            })

    # 2. HW transcode support
    diag["hwaccel"] = Path("/dev/dri").exists() and any(Path("/dev/dri").iterdir())

    # 3. SQLite / slow-query grep
    if PLEX_LOG.exists():
        tail = subprocess.run(
            ["tail", "-n", str(tail_lines), str(PLEX_LOG)],
            check=True, capture_output=True, text=True,
        ).stdout
        for line in tail.splitlines():
            for pat in SQLITE_PATTERNS:
                if pat.search(line):
                    diag["db_warnings"].append(line.strip()[:240])
                    break

    diag["summary"] = {
        "active_sessions": len(diag["sessions"]),
        "transcodes":      sum(1 for s in diag["sessions"]
                               if "transcode" in (s["video_decision"], s["audio_decision"])),
        "hw_transcode_capable": diag["hwaccel"],
        "db_warning_count": len(diag["db_warnings"]),
    }
    return diag
```

#### 3.2 *Arr Stack (Docker)

**`tools/arr_tool.py`:**

```python
import os, httpx
from typing import Literal

SERVICES = {
    "sonarr": (os.environ["SONARR_URL"], os.environ["SONARR_API_KEY"]),
    "radarr": (os.environ["RADARR_URL"], os.environ["RADARR_API_KEY"]),
}

def _headers(key: str) -> dict:
    return {"X-Api-Key": key, "Accept": "application/json"}

async def arr_queue(service: Literal["sonarr", "radarr"]) -> list[dict]:
    base, key = SERVICES[service]
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(f"{base}/api/v3/queue", headers=_headers(key),
                        params={"pageSize": 100, "includeUnknownSeriesItems": True})
        r.raise_for_status()
        return r.json()["records"]

async def arr_health(service: str) -> list[dict]:
    base, key = SERVICES[service]
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(f"{base}/api/v3/health", headers=_headers(key))
        r.raise_for_status()
        return r.json()

async def arr_rootfolders(service: str) -> list[dict]:
    base, key = SERVICES[service]
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(f"{base}/api/v3/rootfolder", headers=_headers(key))
        r.raise_for_status()
        return r.json()

async def diagnose_import_failures(service: str) -> dict:
    """Cross-references rootfolder paths against queue items stuck in 'warning'."""
    queue, roots = await arr_queue(service), await arr_rootfolders(service)
    root_paths = [r["path"] for r in roots]

    stuck = [q for q in queue
             if q.get("trackedDownloadStatus") == "warning"
             or "import" in (q.get("errorMessage") or "").lower()]

    mismatches = []
    for q in stuck:
        out = (q.get("outputPath") or "")
        if out and not any(out.startswith(rp) for rp in root_paths):
            mismatches.append({
                "title": q.get("title"),
                "output_path": out,
                "root_paths": root_paths,
                "status_msgs": [m["title"] for m in q.get("statusMessages", [])],
                "diagnosis": "outputPath is not under any configured rootFolder — "
                             "likely a Docker volume-mount mismatch between *arr and the download client.",
            })

    return {
        "service": service,
        "queue_size": len(queue),
        "warnings": len(stuck),
        "import_mismatches": mismatches,
        "health_issues": await arr_health(service),
    }
```

For `PUT /api/v3/qualityprofile/{id}`, wrap with a Pydantic model and require a `confirm=True` parameter, since it's a write operation affecting future grabs.

#### 3.3 Observability (Tautulli + Overseerr)

**`tools/observability_tool.py`:**

```python
import os, httpx
from datetime import datetime
from typing import Any

TAUTULLI_URL = os.environ["TAUTULLI_URL"]
TAUTULLI_KEY = os.environ["TAUTULLI_API_KEY"]
OVERSEERR_URL = os.environ["OVERSEERR_URL"]
OVERSEERR_KEY = os.environ["OVERSEERR_API_KEY"]

async def tautulli(cmd: str, **params) -> Any:
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(f"{TAUTULLI_URL}/api/v2",
                        params={"apikey": TAUTULLI_KEY, "cmd": cmd, **params})
        r.raise_for_status()
        return r.json()["response"]["data"]

async def overseerr(path: str, **params) -> Any:
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(f"{OVERSEERR_URL}/api/v1/{path.lstrip('/')}",
                        params=params, headers={"X-Api-Key": OVERSEERR_KEY})
        r.raise_for_status()
        return r.json()

async def fault_timeline(window_minutes: int = 60) -> list[dict]:
    """Merge Tautulli buffer/error events, Overseerr failed requests, and
       *Arr import warnings into one timestamped timeline for LLM RCA."""
    cutoff = datetime.utcnow().timestamp() - window_minutes * 60
    events: list[dict] = []

    # Tautulli — recent history
    hist = await tautulli("get_history", length=200)
    for row in (hist.get("data") or []):
        if row["stopped"] and row["stopped"] >= cutoff:
            events.append({
                "ts": int(row["stopped"]),
                "source": "tautulli",
                "user": row["friendly_name"],
                "media": row["full_title"],
                "decision": row["transcode_decision"],
                "state": row.get("state"),
                "session_key": row.get("session_key"),
            })

    # Overseerr — failed requests
    failed = await overseerr("request", filter="failed", take=50, sort="modified")
    for req in failed.get("results", []):
        ts = datetime.fromisoformat(req["updatedAt"].replace("Z", "+00:00")).timestamp()
        if ts >= cutoff:
            events.append({
                "ts": int(ts),
                "source": "overseerr",
                "media": req.get("media", {}).get("tmdbId"),
                "status": req["status"],
                "requested_by": req["requestedBy"]["displayName"],
            })

    # Overseerr status / version skew
    status = await overseerr("status")
    if status.get("commitsBehind", 0) > 50:
        events.append({"ts": int(datetime.utcnow().timestamp()),
                       "source": "overseerr", "alert": "stale_version",
                       "commits_behind": status["commitsBehind"]})

    return sorted(events, key=lambda e: e["ts"])
```

---

### 4. Networking & Proactive Alerting

#### 4.1 DNS & Network Scanning

**`tools/network_tool.py`:**

```python
import os, ipaddress, subprocess
import httpx, nmap

PIHOLE_URL  = os.environ["PIHOLE_URL"]
PIHOLE_AUTH = os.environ["PIHOLE_AUTH"]   # web API token from Pi-hole settings

PRIVATE_NETS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
]

def _is_rfc1918(target: str) -> bool:
    try:
        net = ipaddress.ip_network(target, strict=False)
    except ValueError:
        return False
    return any(net.subnet_of(p) for p in PRIVATE_NETS)

# ── Pi-hole ──
async def pihole_summary() -> dict:
    async with httpx.AsyncClient(timeout=10) as c:
        # Note: post Nov-2022 Pi-hole change, ?summary now also needs ?auth=
        r = await c.get(f"{PIHOLE_URL}/admin/api.php",
                        params={"summary": "", "auth": PIHOLE_AUTH})
        r.raise_for_status()
        return r.json()

async def pihole_recent_blocked(n: int = 10) -> list[str]:
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(f"{PIHOLE_URL}/admin/api.php",
                        params={"recentBlocked": n, "auth": PIHOLE_AUTH})
        r.raise_for_status()
        return r.text.splitlines()

async def pihole_all_queries(limit: int = 200) -> list[list]:
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(f"{PIHOLE_URL}/admin/api.php",
                        params={"getAllQueries": limit, "auth": PIHOLE_AUTH})
        r.raise_for_status()
        return r.json().get("data", [])

# ── Unbound ──
def unbound_stats() -> dict[str, str]:
    out = subprocess.run(
        ["unbound-control", "stats_noreset"],
        check=True, capture_output=True, text=True,
    ).stdout
    return dict(line.split("=", 1) for line in out.splitlines() if "=" in line)

# ── Nmap (RFC1918-restricted) ──
class ScanNotAllowed(Exception): ...

def nmap_host_discovery(subnet: str) -> list[dict]:
    if not _is_rfc1918(subnet):
        raise ScanNotAllowed(f"Refusing to scan non-RFC1918 subnet: {subnet}")
    nm = nmap.PortScanner()
    nm.scan(hosts=subnet, arguments="-sn -T4 --max-retries 1")
    return [
        {"ip": h, "hostname": nm[h].hostname(), "state": nm[h].state(),
         "mac": nm[h]["addresses"].get("mac"),
         "vendor": (nm[h].get("vendor") or {}).get(nm[h]["addresses"].get("mac"))}
        for h in nm.all_hosts()
    ]

def nmap_service_detect(host: str) -> dict:
    if not _is_rfc1918(host):
        raise ScanNotAllowed(f"Refusing to scan non-RFC1918 host: {host}")
    nm = nmap.PortScanner()
    nm.scan(hosts=host, arguments="-sV -p 22,80,443,8080,8443 --version-intensity 5 -T4")
    if host not in nm.all_hosts():
        return {"host": host, "state": "down", "services": []}
    services = []
    for proto in nm[host].all_protocols():
        for port, info in nm[host][proto].items():
            services.append({"port": port, "proto": proto, "state": info["state"],
                             "service": info["name"], "product": info.get("product"),
                             "version": info.get("version")})
    return {"host": host, "state": nm[host].state(), "services": services}
```

#### 4.2 Background Monitoring (Celery 5 + Redis)

**`workers/celeryconfig.py`:**

```python
import os
from celery.schedules import crontab

broker_url     = os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/0")
result_backend = os.environ.get("CELERY_RESULT_BACKEND", "redis://redis:6379/1")

task_serializer       = "json"
result_serializer     = "json"
accept_content        = ["json"]
timezone              = "UTC"
enable_utc            = True
task_track_started    = True
task_acks_late        = True
worker_prefetch_multiplier = 1
broker_connection_retry_on_startup = True
result_expires        = 3600 * 24

imports = ("workers.tasks",)

task_routes = {
    "workers.tasks.scan_subnet":    {"queue": "scans"},
    "workers.tasks.scan_rogue_mac": {"queue": "scans"},
}

beat_schedule = {
    "container-health-60s": {
        "task": "workers.tasks.check_container_health",
        "schedule": 60.0,
    },
    "storage-threshold-5min": {
        "task": "workers.tasks.check_storage_thresholds",
        "schedule": 300.0,
        "kwargs": {"threshold_pct": 85},
    },
    "rogue-mac-scan-15min": {
        "task": "workers.tasks.scan_rogue_mac",
        "schedule": 900.0,
        "kwargs": {"subnet": "192.168.1.0/24"},
    },
    "arr-import-failure-10min": {
        "task": "workers.tasks.check_arr_imports",
        "schedule": 600.0,
    },
    "plex-db-health-30min": {
        "task": "workers.tasks.check_plex_db",
        "schedule": crontab(minute="*/30"),
    },
}
```

**`workers/app.py`:**

```python
from celery import Celery
app = Celery("homelab_agent")
app.config_from_object("workers.celeryconfig")
```

**`workers/tasks.py`:**

```python
import asyncio, json
from celery import shared_task
from tools.docker_tool import list_containers, client as docker_client
from tools.proxmox_tool import storage_usage
from tools.network_tool import nmap_host_discovery
from tools.arr_tool import diagnose_import_failures
from tools.plex_tool import diagnose_plex
from agent.alerts.telegram import send_alert
import redis

_redis = redis.Redis.from_url("redis://redis:6379/2")

@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def check_container_health(self):
    bad = []
    for c in list_containers():
        if c["status"] not in ("running", "healthy"):
            logs = docker_client.containers.get(c["id"]).logs(tail=10).decode("utf-8", "ignore")
            bad.append({**c, "tail": logs})
    if bad:
        asyncio.run(send_alert("container_crash", bad))
    return {"unhealthy": len(bad)}

@shared_task
def check_storage_thresholds(threshold_pct: int = 85):
    over = [s for s in storage_usage(node="pve")
            if s["used_pct"] and s["used_pct"] >= threshold_pct]
    if over:
        asyncio.run(send_alert("storage_threshold", {"threshold": threshold_pct, "volumes": over}))
    return over

@shared_task
def scan_rogue_mac(subnet: str):
    seen = nmap_host_discovery(subnet)
    known = set(json.loads(_redis.get("known_macs") or "[]"))
    rogue = [h for h in seen if h["mac"] and h["mac"].lower() not in known]
    for h in rogue:
        _redis.sadd("first_seen", json.dumps({"mac": h["mac"], "ip": h["ip"]}))
        asyncio.run(send_alert("rogue_mac", h))
    return rogue

@shared_task
def check_arr_imports():
    for svc in ("sonarr", "radarr"):
        diag = asyncio.run(diagnose_import_failures(svc))
        if diag["import_mismatches"]:
            asyncio.run(send_alert("arr_import_mismatch", diag))

@shared_task
def check_plex_db():
    diag = asyncio.run(diagnose_plex())
    if diag["summary"]["db_warning_count"] > 5:
        asyncio.run(send_alert("plex_db_warning", diag))
```

#### 4.3 Telegram Alerts

**`agent/alerts/telegram.py`:**

```python
import os
from telegram import Bot
from telegram.constants import ParseMode
from telegram.helpers import escape_markdown

BOT = Bot(token=os.environ["TELEGRAM_BOT_TOKEN"])
CHAT_ID = int(os.environ["TELEGRAM_CHAT_ID"])

def _esc(s) -> str:
    return escape_markdown(str(s), version=2)

TEMPLATES = {
    "storage_threshold": lambda p: (
        f"🟠 *Storage threshold breached* \\({_esc(p['threshold'])}%\\)\n"
        + "\n".join(f"• `{_esc(v['id'])}` — *{_esc(v['used_pct'])}%* "
                    f"\\({_esc(v['used_gb'])}/{_esc(v['total_gb'])} GB\\)"
                    for v in p["volumes"])
    ),
    "container_crash": lambda containers: "\n\n".join(
        f"🔴 *Container down*: `{_esc(c['name'])}` \\(status: {_esc(c['status'])}\\)\n"
        f"```\n{_esc(c['tail'][-1500:])}\n```"
        for c in containers
    ),
    "rogue_mac": lambda h: (
        f"⚠️ *Unknown MAC on LAN*\n"
        f"• MAC: `{_esc(h['mac'])}`\n"
        f"• IP: `{_esc(h['ip'])}`\n"
        f"• Vendor: {_esc(h.get('vendor') or 'unknown')}\n"
        f"• Hostname: `{_esc(h.get('hostname') or '—')}`\n"
        f"• First seen: {_esc(__import__('datetime').datetime.utcnow().isoformat(timespec='seconds'))} UTC"
    ),
    "arr_import_mismatch": lambda d: (
        f"📥 *{_esc(d['service'].title())} import mismatch* "
        f"\\({_esc(len(d['import_mismatches']))} item\\(s\\)\\)\n"
        + "\n".join(f"• `{_esc(m['title'][:80])}` → `{_esc(m['output_path'])}`"
                    for m in d["import_mismatches"][:5])
    ),
    "plex_db_warning": lambda d: (
        f"🟡 *Plex SQLite warnings* \\({_esc(d['summary']['db_warning_count'])}\\)\n"
        + "```\n" + _esc("\n".join(d["db_warnings"][:5])) + "\n```"
    ),
}

async def send_alert(kind: str, payload) -> None:
    text = TEMPLATES[kind](payload)
    # MarkdownV2 max 4096 chars per message
    for chunk_start in range(0, len(text), 3900):
        await BOT.send_message(
            chat_id=CHAT_ID,
            text=text[chunk_start:chunk_start + 3900],
            parse_mode=ParseMode.MARKDOWN_V2,
            disable_web_page_preview=True,
        )
```

---

### 5. Repository Structure

```
homelab-agent/
├── README.md
├── pyproject.toml                       # ruff, mypy, pytest, hatch build
├── requirements.txt                     # runtime pins (fastapi, litellm, instructor, pydantic>=2.6, ...)
├── requirements-dev.txt
├── .env.example
├── .github/
│   └── workflows/
│       ├── ci.yml                       # lint + test + build container
│       └── release.yml                  # ghcr.io push on tag
│
├── ui/                                  # Next.js 14 (App Router) control plane
│   ├── package.json
│   ├── next.config.mjs
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx                     # dashboard: container/LXC/storage tiles
│   │   ├── chat/page.tsx                # conversational agent UI (streaming SSE)
│   │   ├── alerts/page.tsx              # alert history + ack
│   │   ├── settings/
│   │   │   ├── page.tsx
│   │   │   └── providers/page.tsx       # API-key entry, model picker
│   │   └── api/                         # Next route handlers proxying to FastAPI
│   │       ├── chat/route.ts
│   │       └── tools/[name]/route.ts
│   ├── components/                      # ServiceTile, LogStream, ToolCallCard
│   ├── lib/
│   │   ├── api-client.ts                # typed fetch wrapper
│   │   └── zod-schemas.ts               # imports from ../schemas/zod
│   └── public/
│
├── agent/                               # FastAPI backend + LiteLLM + tool registry
│   ├── __init__.py
│   ├── main.py                          # FastAPI app, /chat, /tools/*, /healthz
│   ├── settings.py                      # pydantic-settings, env loader
│   ├── llm/
│   │   ├── client.py                    # LLMClient (Section 1.1)
│   │   ├── router_config.yaml
│   │   └── prompts/
│   │       ├── system.md                # agent persona + safety rules
│   │       └── tool_use_examples.md
│   ├── tools/
│   │   ├── base.py                      # ToolSpec, parse_tool_args (Section 1.2)
│   │   └── registry.py                  # decorator-driven tool registration
│   ├── alerts/
│   │   ├── telegram.py                  # Section 4.3
│   │   └── dispatcher.py                # routes alerts to telegram / discord / smtp
│   ├── orchestrator.py                  # agent loop: LLM → tool → LLM
│   └── auth.py                          # FastAPI dependencies: bearer JWT
│
├── tools/                               # importable tool modules (own package for testability)
│   ├── __init__.py
│   ├── docker_tool.py                   # Section 2.1
│   ├── portainer_tool.py                # Section 2.2
│   ├── proxmox_tool.py                  # Section 2.3
│   ├── plex_tool.py                     # Section 3.1
│   ├── arr_tool.py                      # Section 3.2 (sonarr + radarr)
│   ├── observability_tool.py            # Section 3.3 (tautulli + overseerr)
│   ├── network_tool.py                  # Section 4.1 (pihole, unbound, nmap)
│   └── tests/
│       ├── conftest.py                  # httpx_mock fixtures
│       ├── test_docker_tool.py
│       └── test_arr_tool.py
│
├── workers/                             # Celery + beat
│   ├── __init__.py
│   ├── app.py                           # Celery() instance
│   ├── celeryconfig.py                  # Section 4.2 (beat_schedule, routing)
│   └── tasks.py                         # @shared_task functions
│
├── iac/                                 # all deployable artefacts
│   ├── compose/
│   │   ├── docker-compose.yml           # Section 1.3.1
│   │   ├── .env.example
│   │   └── socket-proxy.override.yml
│   ├── lxc/
│   │   ├── install-homelab-agent.sh     # tteck-style bootstrap (Section 1.3.2)
│   │   ├── install/homelab-agent-install.sh
│   │   └── systemd/homelab-agent.service
│   ├── ansible/
│   │   ├── inventory.yml
│   │   ├── playbook.yml                 # idempotent install for bare metal / LXC
│   │   └── roles/
│   │       ├── docker/tasks/main.yml
│   │       └── agent/tasks/main.yml
│   └── proxmox/
│       └── create-api-token.sh          # pveum commands from Section 2.3
│
└── schemas/                             # cross-layer contracts (Pydantic + Zod)
    ├── python/
    │   ├── __init__.py
    │   ├── docker.py                    # ContainerAction, ContainerInfo, ...
    │   ├── proxmox.py                   # LxcMigrate, StorageUsage, ...
    │   ├── arr.py                       # QueueRecord, RootFolder, ...
    │   ├── alerts.py                    # AlertEnvelope discriminated union
    │   └── chat.py                      # ChatMessage, ToolCall, ToolResult
    ├── zod/
    │   ├── index.ts
    │   ├── docker.ts
    │   ├── proxmox.ts
    │   ├── arr.ts
    │   └── alerts.ts
    └── generate.py                      # python -> json-schema -> zod codegen
```

---

## Recommendations

1. **Stage 1 — read-only deployment (week 1).** Spin up the LXC, install with the community-scripts/tteck-style script, configure the Proxmox token with `VM.Audit` + `Datastore.Audit` + `Sys.Audit` ONLY (omit `VM.Migrate` initially). Confirm Pi-hole/Plex/Sonarr/Radarr diagnostic tools work end-to-end. **Benchmark to advance:** agent answers "what's broken right now?" with correct, non-hallucinated tool output for 5 consecutive scenarios.
2. **Stage 2 — gated writes (week 2-3).** Add `VM.Migrate` to the PVE role, set `ALLOW_RESTARTS=1` on the socket proxy, enable the Sonarr/Radarr queue-deletion tool. Require human confirmation in chat ("type `confirm` to proceed") for every write. **Benchmark to advance:** zero unintended writes over a 7-day soak.
3. **Stage 3 — autonomous remediation (week 4+).** Allow specific Celery tasks (restart a container that has crashed >3× in 10 min, snapshot Plex DB on SQLite-warning spikes) to execute writes without confirmation, but emit Telegram receipts for every action. **Benchmark to advance:** mean time to remediation < 90 seconds for the top-3 recurring incidents.
4. **If the local LLM (Ollama) JSON failure rate exceeds 15% on tool calls**, switch the correction-loop fallback to a hosted model by raising `max_attempts` to 5 OR routing tool-arg correction explicitly to a cheap fast hosted model (e.g., `anthropic/claude-haiku-4-5`).
5. **Pin Pi-hole API to v5 syntax for now;** when upgrading to Pi-hole v6, swap the `network_tool.py` Pi-hole functions to the new `/api/` REST endpoints (`Authorization: Bearer <sid>` header instead of `?auth=` query param).
6. **Rotate the Proxmox token quarterly** by setting `--expire $(date -d '+90 days' +%s)` on `pveum user token add`. The agent will surface a `401` and Telegram-alert; rotation is a one-command operation.

---

## Caveats

- **Docker socket proxy still grants effective root inside the proxy's network.** Never bind its port to a public interface; the `socket-proxy-net` network in the compose file is marked `internal: true` for this reason.
- **`tecnativa/docker-socket-proxy` does not filter responses by container label** — any caller that can hit `/containers/json` sees ALL containers including their env vars (which often contain secrets). For multi-tenant isolation, layer `wollomatic/socket-proxy` (regex path allow-listing) or `FoxxMD/docker-proxy-filter` underneath.
- **Pi-hole's `getAllQueries` can return tens of thousands of rows.** Always cap with a `limit` parameter and stream/paginate — do not feed raw query dumps into LLM context. Per the official Pi-hole blog post "Upcoming changes: authentication for more API endpoints required" (November 17, 2022), even the previously-public `summary`, `summaryRaw`, `status`, and `overTimeData10mins` endpoints now require `?auth=<token>`, so set `PIHOLE_AUTH` for every call.
- **`pct migrate` between PVE nodes requires either offline state or `--restart 1`** (no live LXC migration). The agent's `migrate_lxc` defaults to `restart=True`; expect 100-500 ms of downtime per migration.
- **LiteLLM `enforce_model_rate_limits` is best-effort for TPM**, exact for RPM. Per the user report in BerriAI/litellm GitHub issue #10052 (v1.66.0): *"For a model configured with a model_tpm_limit of 2000 TPM, I consistently receive a 429 error only after exceeding the limit by approximately 1000 tokens (i.e., around 3000 tokens are processed within the minute before the 429 occurs)."* Tune `rpm` rather than `tpm` for hard guarantees.
- **`python-telegram-bot` is fully async, but the supported Python minimum has shifted.** Per the official python-telegram-bot.org docs, v20.x supports Python 3.8+; the current latest release on PyPI (v22.7) requires Python 3.10+. Pin your version accordingly. Mixing it with sync Celery tasks (as shown in `workers/tasks.py`) requires `asyncio.run(...)` per task; for high alert volumes, switch the worker to `--pool=gevent` or run a dedicated async dispatcher.
- **community-scripts/ProxmoxVE is community-maintained** following tteck's passing in mid-November 2024 — per the maintainer note on community-scripts/ProxmoxVE Discussion #237 (November 14, 2024), his wife Angie posted "he passed away a few days ago," following his October 29, 2024 public announcement of metastatic appendiceal cancer and entry into hospice care. Audit any sourced `build.func` revision pin before production use — the upstream evolves quickly and has changed default `var_version` for Debian from 12 → 13 in mid-2025.
- **The Overseerr API has a confirmed open issue.** sct/overseerr#4167, opened June 25, 2025 by user glacialcalamity, reports: *"Filter Ineffectiveness: API filter parameters (filter=pending, filter=declined, etc.) return identical datasets regardless of filter type"* and *"Missing Declined Requests: Requests visible as Declined in UI are not returned by API calls at all."* Cross-reference with the `media.status` field (5 = `AVAILABLE`, 4 = `PARTIALLY_AVAILABLE`, 2 = `PENDING`) for canonical state until this is fixed upstream.