# Proxmox Permissions

Foxhole should use a dedicated Proxmox API token. Stage 1 grants audit-only permissions so diagnostics can inspect state without power, allocation, console, or configuration privileges.

Run on a Proxmox node:

```bash
sudo iac/proxmox/create-api-token.sh
```

The script creates or updates:

- User: `homelab-agent@pve`
- Role: `HomelabAgent`
- ACL path: `/`
- Token: `homelab-agent@pve!foxhole`

Stage 1 privileges:

```text
Sys.Audit VM.Audit Datastore.Audit SDN.Audit
```

Stage 2 can optionally add `VM.Migrate` for a future confirmed LXC migration tool:

```bash
sudo FOXHOLE_PROXMOX_ALLOW_MIGRATE=true iac/proxmox/create-api-token.sh
```

The token is created with `--privsep 0`. That is intentional: the token inherits the user role assignment above, which keeps review focused on the `HomelabAgent` role and ACL.

Proxmox prints a token secret only when the token is first created. Save it directly into `/etc/homelab-agent/foxhole.env` or a password manager:

```text
FOXHOLE_PROXMOX_TOKEN_ID=homelab-agent@pve!foxhole
FOXHOLE_PROXMOX_TOKEN_SECRET=<secret>
```

Do not grant `VM.PowerMgmt`, `VM.Allocate`, `Datastore.Allocate`, `Sys.Modify`, or `Permissions.Modify` to the Foxhole role.

