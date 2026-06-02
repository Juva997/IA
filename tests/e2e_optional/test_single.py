import os
import shutil
import tempfile
from pathlib import Path

import pytest

from benchmark.runtime import build_benchmark_engine


CASES = [
    {
        "name": "resolucao_problemas",
        "input": "como resolver o problema das 8 rainhas no xadrez?",
        "verify": {"output_contains_any": ["rainhas", "backtracking", "algoritmo"]},
    },
    {
        "name": "codigo",
        "input": "criar script python que imprime números de 1 a 5",
        "verify": {
            "glob_exists": ["**/*.py"],
            "output_contains_any": ["print", "for", "range"],
        },
    },
    {
        "name": "processamento_csv",
        "input": "crie um arquivo de texto com dados numéricos separados por vírgula",
        "verify": {
            "glob_exists": ["**/*.txt"],
            "output_contains_any": ["dados", "números", "1,2,3"],
        },
    },
    {
        "name": "estatisticas",
        "input": "gere 100 números aleatórios e calcule média, mediana e desvio padrão",
        "verify": {"output_contains_any": ["média", "mediana", "desvio"]},
    },
    {
        "name": "ambiguous_clarify",
        "input": "faz isso pra mim",
        "verify": {"output_contains_any": ["?", "detalhes"]},
    },
    {
        "name": "format_json",
        "input": "Responda somente em JSON valido: nome=Joao, idade=20",
        "verify": {"output_contains_any": ['"nome"', "Joao"]},
    },
    {
        "name": "format_table",
        "input": "Responda em tabela markdown com nome=Joao e idade=20",
        "verify": {"output_contains_any": ["| nome | idade |", "Joao"]},
    },
    {
        "name": "logic_transitive",
        "input": "Se todos A sao B e todos B sao C, A e C?",
        "verify": {"output_contains_any": ["Sim", "A e C"]},
    },
]


@pytest.mark.e2e_optional
@pytest.mark.parametrize("case", CASES, ids=[case["name"] for case in CASES])
def test_case(case):
    root = tempfile.mkdtemp(prefix="ia_test_")
    original_dir = os.getcwd()
    os.chdir(root)

    try:
        engine = build_benchmark_engine(root, verbose=False)
        result = engine.run(case["input"])
        output = str(result.get("output", "") or result.get("error", ""))

        assert result.get("status") == "success", result
        assert _output_matches(output, case["verify"].get("output_contains_any", []))
        for pattern in case["verify"].get("glob_exists", []):
            assert list(Path(root).glob(pattern)), f"missing glob: {pattern}"
    finally:
        os.chdir(original_dir)
        shutil.rmtree(root, ignore_errors=True)


def _output_matches(output, options):
    if not options:
        return True
    lowered = output.lower()
    return any(str(option).lower() in lowered for option in options)
