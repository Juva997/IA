import os
import shutil

from benchmark.runtime import (
    BenchmarkLLM,
    build_benchmark_engine,
    build_benchmark_memory,
    create_isolated_workspace,
    prepare_workspace,
)


def test_prepare_workspace_copies_config(tmp_path):
    root = prepare_workspace(str(tmp_path))
    try:
        assert os.path.isdir(root)
        assert os.path.exists(os.path.join(root, "config.json"))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_create_isolated_workspace_uses_unique_child(tmp_path):
    first = create_isolated_workspace(str(tmp_path))
    second = create_isolated_workspace(str(tmp_path))
    try:
        assert first != second
        assert os.path.commonpath([first, str(tmp_path)]) == str(tmp_path)
        assert os.path.commonpath([second, str(tmp_path)]) == str(tmp_path)
    finally:
        shutil.rmtree(first, ignore_errors=True)
        shutil.rmtree(second, ignore_errors=True)


def test_benchmark_memory_is_in_memory_only():
    memory = build_benchmark_memory()

    memory.vector_store.add("python benchmark fact")
    context = memory.build_context("python", {"history": []})

    assert "python benchmark fact" in context["retrieved_memory"]


def test_benchmark_llm_returns_offline_response():
    llm = BenchmarkLLM()

    assert llm.generate("goal", "prompt") == "Resposta benchmark sem LLM externo"


def test_build_benchmark_engine_runs_without_old_benchmark_file(tmp_path):
    engine = build_benchmark_engine(str(tmp_path), verbose=False)

    result = engine.run("oi")

    assert result["status"] == "success"
    assert "ajudar" in result["output"].lower()


def test_benchmark_engine_handles_offline_smoke_prompts(tmp_path):
    engine = build_benchmark_engine(str(tmp_path), verbose=False)

    ambiguous = engine.run("faz isso pra mim")
    json_result = engine.run("Responda somente em JSON valido: nome=Joao, idade=20")
    table_result = engine.run("Responda em tabela markdown com nome=Joao e idade=20")
    logic_result = engine.run("Se todos A sao B e todos B sao C, A e C?")

    assert ambiguous["status"] == "success"
    assert "?" in ambiguous["output"]
    assert json_result["output"] == '{"nome":"Joao","idade":20}'
    assert "| nome | idade |" in table_result["output"]
    assert "sim" in logic_result["output"].lower()
