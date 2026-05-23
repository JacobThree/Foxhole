def replace_in_file(path, replacements):
    with open(path) as f:
        content = f.read()
    for k, v in replacements.items():
        content = content.replace(k, v)
    with open(path, 'w') as f:
        f.write(content)

replace_in_file('tests/tools/test_network_tool.py', {
    '"pihole_base_url"': '"pihole_enabled": True, "pihole_base_url"',
    '"unbound_host"': '"unbound_enabled": True, "unbound_host"',
})
replace_in_file('tests/tools/test_arr_tool.py', {
    'sonarr_base_url=': 'sonarr_enabled=True, sonarr_base_url=',
    'radarr_base_url=': 'radarr_enabled=True, radarr_base_url=',
})
replace_in_file('tests/tools/test_arr_actions.py', {
    'sonarr_base_url=': 'sonarr_enabled=True, sonarr_base_url=',
    'radarr_base_url=': 'radarr_enabled=True, radarr_base_url=',
})
replace_in_file('tests/tools/test_plex_tool.py', {
    'plex_base_url=': 'plex_enabled=True, plex_base_url=',
})
replace_in_file('tests/tools/test_portainer_tool.py', {
    'portainer_base_url=': 'portainer_enabled=True, portainer_base_url=',
})
replace_in_file('tests/tools/test_observability_tool.py', {
    'tautulli_base_url=': 'tautulli_enabled=True, tautulli_base_url=',
    'overseerr_base_url=': 'overseerr_enabled=True, overseerr_base_url=',
})
replace_in_file('tests/agent/test_main.py', {
    'api_bearer_token=SecretStr("test-token")': 'api_bearer_token=SecretStr("test-token"), docker_enabled=True, telegram_enabled=True'
})
replace_in_file('tests/agent/test_settings.py', {
    'monkeypatch.setenv("FOXHOLE_PLEX_BASE_URL", "http://plex.local:32400")': 'monkeypatch.setenv("FOXHOLE_PLEX_ENABLED", "true")\n    monkeypatch.setenv("FOXHOLE_PLEX_BASE_URL", "http://plex.local:32400")'
})
