# Portainer Integration

Foxhole supports read-only Portainer diagnostics and a confirmation-gated Git stack redeploy.

Configure an API token first:

```bash
FOXHOLE_PORTAINER_BASE_URL=https://portainer.example.test
FOXHOLE_PORTAINER_API_TOKEN=ptr_xxx
```

If no API token is configured, Foxhole can fall back to username/password JWT auth:

```bash
FOXHOLE_PORTAINER_USERNAME=admin
FOXHOLE_PORTAINER_PASSWORD=change-me
```

Available tools:

- `portainer_list_endpoints`
- `portainer_list_stacks`
- `portainer_stack_details`
- `portainer_redeploy_stack`

`portainer_redeploy_stack` requires `stack_id`, `endpoint_id`, and write-policy confirmation. Use API tokens for normal operation because they are easier to rotate and avoid keeping a user password in the agent config.
