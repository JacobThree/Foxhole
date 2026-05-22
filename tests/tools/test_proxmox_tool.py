from __future__ import annotations

from pydantic import SecretStr

from agent.settings import AppSettings
from tools import proxmox_tool


def test_token_id_is_split_for_proxmoxer() -> None:
    assert proxmox_tool._split_token_id("homelab-agent@pve!foxhole") == (
        "homelab-agent@pve",
        "foxhole",
    )


def test_invalid_token_id_fails_clearly() -> None:
    try:
        proxmox_tool._split_token_id("homelab-agent@pve")
    except ValueError as exc:
        assert "user@realm!token-name" in str(exc)
    else:
        raise AssertionError("invalid token id should fail")


def test_storage_row_reports_percent_and_gb() -> None:
    row = proxmox_tool._storage_row(
        "pve",
        {"storage": "local-zfs", "type": "zfspool", "content": "images", "enabled": 1},
        {"used": 50 * 1_073_741_824, "total": 100 * 1_073_741_824},
    )

    assert row["used_percent"] == 50.0
    assert row["used_gb"] == 50.0
    assert row["total_gb"] == 100.0
    assert row["type"] == "zfspool"


def test_build_client_parses_settings(monkeypatch) -> None:
    calls = {}

    class FakeProxmoxer:
        @staticmethod
        def ProxmoxAPI(host, **kwargs):
            calls["host"] = host
            calls["kwargs"] = kwargs
            return object()

    monkeypatch.setattr(proxmox_tool.importlib, "import_module", lambda name: FakeProxmoxer)
    settings = AppSettings(
        proxmox_host="pve.local",
        proxmox_token_id=SecretStr("homelab-agent@pve!foxhole"),
        proxmox_token_secret=SecretStr("secret"),
        proxmox_verify_ssl=False,
    )

    proxmox_tool.build_proxmox_client(settings)

    assert calls["host"] == "pve.local"
    assert calls["kwargs"]["user"] == "homelab-agent@pve"
    assert calls["kwargs"]["token_name"] == "foxhole"
    assert calls["kwargs"]["token_value"] == "secret"
    assert calls["kwargs"]["verify_ssl"] is False
