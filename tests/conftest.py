from pathlib import Path

import pytest
import os

from bootstrap.container import build_engine

# Ensure tests keep allowing sandbox writes (legacy test expectations)
os.environ.setdefault("SANDBOX_ALLOW_FILE_WRITE", "1")


class FakeLLM:
    def __init__(self, response="Resposta fake"):
        self.response = response
        self.calls = []

    def generate(self, *args):
        self.calls.append(args)
        return self.response


class FakeVectorStore:
    def __init__(self):
        self.items = []

    def add(self, text, metadata=None):
        self.items.append((text, metadata))

    def save(self, path):
        return None

    def load(self, path):
        return None

    def clear(self):
        self.items = []


class FakeRetriever:
    def __init__(self, results=None):
        self.results = list(results or [])

    def retrieve(self, query):
        return list(self.results)


@pytest.fixture
def fake_llm():
    return FakeLLM()


@pytest.fixture
def isolated_workspace(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def deterministic_engine(isolated_workspace, fake_llm):
    return build_engine(
        llm_router=fake_llm,
        persist_path=str(isolated_workspace / "memory"),
        safe_root=str(isolated_workspace),
        debug=False,
        enable_router=False,
    )


def pytest_collection_modifyitems(config, items):
    for item in items:
        parts = set(Path(str(item.fspath)).parts)
        if "unit" in parts:
            item.add_marker(pytest.mark.unit)
        elif "integration" in parts:
            item.add_marker(pytest.mark.integration)
        elif "e2e_optional" in parts:
            item.add_marker(pytest.mark.e2e_optional)
            item.add_marker(pytest.mark.llm)
            item.add_marker(pytest.mark.slow)
