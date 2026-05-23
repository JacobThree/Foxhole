import re

with open('tests/tools/test_network_tool.py', 'r') as f:
    content = f.read()
content = content.replace('"pihole_base_url": "http://pihole.local",', '"pihole_enabled": True,\n        "pihole_base_url": "http://pihole.local",')
content = content.replace('"unbound_host": "unbound.local",', '"unbound_enabled": True,\n        "unbound_host": "unbound.local",')
with open('tests/tools/test_network_tool.py', 'w') as f:
    f.write(content)

with open('tests/tools/test_arr_tool.py', 'r') as f:
    content = f.read()
content = content.replace('sonarr_enabled=True, sonarr_base_url', 'sonarr_enabled=True, sonarr_base_url') # Was already replaced? Wait.
with open('tests/tools/test_arr_tool.py', 'w') as f:
    f.write(content)

with open('tests/agent/test_main.py', 'r') as f:
    content = f.read()
content = content.replace('api_bearer_token=SecretStr("test-token"),', 'api_bearer_token=SecretStr("test-token"),\n        docker_enabled=True, docker_socket_proxy_url="tcp://mock",\n        telegram_enabled=True, telegram_bot_token=SecretStr("t")')
with open('tests/agent/test_main.py', 'w') as f:
    f.write(content)

with open('tests/tools/test_observability_tool.py', 'r') as f:
    content = f.read()
# Replace overseerr_enabled=True for mock settings inside test_overseerr_uses_x_api_key_header etc
content = content.replace('overseerr_base_url', 'overseerr_enabled=True, overseerr_base_url')
with open('tests/tools/test_observability_tool.py', 'w') as f:
    f.write(content)
