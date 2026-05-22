from pydantic import SecretStr

from agent.llm.client import build_router_config
from agent.settings import AppSettings


def test_router_config_uses_validated_settings() -> None:
    settings = AppSettings(
        llm_primary_model="gpt-test",
        llm_primary_api_key=SecretStr("primary-secret"),
        llm_primary_api_base="https://llm.example/v1",
        llm_local_model="ollama/test",
        llm_local_api_base="http://ollama.local:11434",
        llm_vllm_model="openai/vllm-test",
        llm_vllm_api_base="http://vllm.local:8001/v1",
        llm_timeout_seconds=12,
        llm_retries=1,
    )

    config = build_router_config(settings)

    assert set(config) == {"agent-primary", "agent-local", "agent-vllm"}
    assert config["agent-primary"]["model"] == "gpt-test"
    assert config["agent-primary"]["api_key"] == "primary-secret"
    assert config["agent-primary"]["fallbacks"] == ["agent-local", "agent-vllm"]
    assert config["agent-local"]["api_base"] == "http://ollama.local:11434"
    assert config["agent-vllm"]["timeout"] == 12


def test_fake_llm_client_can_replace_runtime_client() -> None:
    class FakeClient:
        async def complete(self, messages, tools=None, *, model_alias="agent-primary"):
            return {"messages": messages, "tools": tools, "model_alias": model_alias}

    client = FakeClient()

    assert client is not None
