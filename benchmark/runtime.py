import inspect
import os
import shutil
import tempfile
from pathlib import Path

from bootstrap.container import build_engine
from memory.memory import Memory


class BenchmarkVectorStore:
    def __init__(self):
        self.items = []

    def add(self, text, metadata=None):
        self.items.append({"text": text, "metadata": metadata or {}})

    def search(self, query, top_k=5):
        query_text = str(query or "").lower()
        matches = [
            item
            for item in self.items
            if query_text and query_text in str(item.get("text", "")).lower()
        ]
        return matches[:top_k]

    def save(self, path):
        return None

    def load(self, path):
        return None

    def clear(self):
        self.items = []


class BenchmarkRetriever:
    def __init__(self, vector_store):
        self.vector_store = vector_store

    def retrieve(self, query):
        return [item["text"] for item in self.vector_store.search(query)]


class BenchmarkMemory(Memory):
    def _save(self):
        return None

    def _load_if_exists(self):
        return None


class BenchmarkLLM:
    def generate(self, *args):
        return "Resposta benchmark sem LLM externo"


def build_benchmark_memory():
    vector_store = BenchmarkVectorStore()
    return BenchmarkMemory(vector_store, BenchmarkRetriever(vector_store))


def prepare_workspace(workspace_dir=None, prefix="ia_benchmark_"):
    if workspace_dir:
        os.makedirs(workspace_dir, exist_ok=True)
        root = tempfile.mkdtemp(prefix=prefix, dir=workspace_dir)
    else:
        root = tempfile.mkdtemp(prefix=prefix)

    original_config = _project_root() / "config.json"
    if original_config.exists():
        shutil.copyfile(original_config, Path(root) / "config.json")

    return root


def create_isolated_workspace(base="benchmark_workspace", prefix="ia_benchmark_"):
    return prepare_workspace(base, prefix=prefix)


def build_benchmark_engine(
    root,
    use_external_llm=False,
    verbose=False,
    enable_router=False,
    llm_router=None,
    memory=None,
):
    kwargs = {
        "memory": memory or build_benchmark_memory(),
        "persist_path": os.path.join(root, "data", "vectors", "memory"),
        "safe_root": root,
        "debug": verbose,
        "enable_router": enable_router,
    }
    if llm_router is not None:
        kwargs["llm_router"] = llm_router
    elif not use_external_llm:
        kwargs["llm_router"] = BenchmarkLLM()

    return build_engine(**_supported_build_engine_kwargs(kwargs))


def _supported_build_engine_kwargs(kwargs):
    try:
        signature = inspect.signature(build_engine)
    except (TypeError, ValueError):
        return {}

    parameters = signature.parameters
    accepts_kwargs = any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD
        for parameter in parameters.values()
    )
    return {
        key: value
        for key, value in kwargs.items()
        if accepts_kwargs or key in parameters
    }


def _project_root():
    return Path(__file__).resolve().parent.parent
