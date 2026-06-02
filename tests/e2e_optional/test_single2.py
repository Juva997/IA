import os
import shutil
import tempfile
from pathlib import Path

import pytest

from benchmark.runtime import build_benchmark_engine


CASES = [
    {
        "name": "planejamento_complexo",
        "input": "criar sistema em python com arquivo que gera número aleatório e salva em txt",
        "verify": {
            "glob_exists": ["**/*.py"],
            "output_contains_any": ["random", "arquivo", "txt", "python"],
        },
    },
    {
        "name": "debug_codigo",
        "input": "crie um código python simples que funcione corretamente",
        "verify": {"output_contains_any": ["print", "def", "saudacao"]},
    },
    {
        "name": "refatoracao",
        "input": "crie um código python simples e funcional",
        "verify": {"output_contains_any": ["def", "print", "return"]},
    },
    {
        "name": "evolucao_codigo",
        "input": "crie uma versão melhorada deste código: print('hello')",
        "verify": {"output_contains_any": ["def", "mostrar_mensagem", "hello"]},
    },
    {
        "name": "benchmark_python",
        "input": "crie um exemplo simples de benchmark em python",
        "verify": {
            "glob_exists": ["**/benchmark_exemplo.py"],
            "output_contains_any": ["benchmark", "performance"],
        },
    },
    {
        "name": "folder_file_roundtrip",
        "input": "crie uma pasta chamada projeto, dentro crie arquivo resultado.txt com ok e depois leia",
        "verify": {
            "glob_exists": ["**/resultado.txt"],
            "output_contains_any": ["ok"],
        },
    },
    {
        "name": "factorial_script",
        "input": "crie um script python de fatorial",
        "verify": {
            "glob_exists": ["**/fatorial.py"],
            "output_contains_any": ["fatorial", "resultado"],
        },
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
