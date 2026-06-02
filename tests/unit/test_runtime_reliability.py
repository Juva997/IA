from bootstrap.container import _model_setup
from cognition.agent import Agent


class FakeClient:
    def generate(self, *args):
        return "ok"


class FakeConfig:
    def __init__(self, values):
        self.values = values

    def get(self, key, default=None):
        return self.values.get(key, default)


def test_model_setup_resolves_missing_power_model(monkeypatch):
    def fake_discover(base_url, timeout, probe_model):
        return ["phi3:mini", "qwen2.5:3b", "qwen2.5-coder:7b"]

    monkeypatch.setattr("bootstrap.container._discover_ollama_models", fake_discover)
    config = FakeConfig(
        {
            "llm.fast_model": "phi3:mini",
            "llm.default_model": "qwen2.5:3b",
            "llm.power_model": "qwen2.5:7b",
        }
    )

    info = _model_setup(config, "http://localhost:11434/api/generate", 15)

    assert info["resolved"]["power"] == "qwen2.5-coder:7b"
    assert info["missing_configured_models"] == {"power": "qwen2.5:7b"}


def test_agent_completion_detects_final_and_pending_steps():
    agent = Agent(FakeClient())

    assert agent.check_completion(
        "crie arquivo a.txt",
        {"history": [{"step": {"action": "write_file"}, "result": {}}]},
        {"status": "success", "output": "arquivo criado"},
    )
    assert not agent.check_completion(
        "crie arquivo a.txt e leia",
        {"history": [{"step": {"action": "write_file"}, "result": {}}]},
        {"status": "success", "output": "arquivo criado"},
    )
    assert agent.check_completion(
        "crie arquivo a.txt e leia",
        {"history": [{"step": {"action": "read_file"}, "result": {}}]},
        {"status": "success", "output": "conteudo"},
    )
