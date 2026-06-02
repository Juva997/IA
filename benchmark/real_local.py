import json
from pathlib import Path


DATASET_DIR = Path(__file__).resolve().parent / "datasets"
CURATED_PATH = DATASET_DIR / "real_local.json"
# Target total cases (curated + generated). 300 is a good balance for heavy, real-local tests.
TARGET_REAL_LOCAL_CASES = 300


def load_real_local_dataset(target_size=TARGET_REAL_LOCAL_CASES):
    curated = _load_curated()
    generated = generate_real_local_cases(max(0, int(target_size) - len(curated)))
    return curated + generated


def generate_real_local_cases(count):
    cases = []
    for index in range(int(count or 0)):
        t = index % 10
        if t == 0:
            cases.append(_generated_nested_file_case(index))
        elif t == 1:
            cases.append(_generated_csv_case(index))
        elif t == 2:
            cases.append(_generated_read_fixture_case(index))
        elif t == 3:
            cases.append(_generated_text_file_case(index))
        elif t == 4:
            cases.append(_generated_python_exec_case(index))
        elif t == 5:
            cases.append(_generated_python_module_case(index))
        elif t == 6:
            cases.append(_generated_pytest_case(index))
        elif t == 7:
            cases.append(_generated_pytest_case(index))
        elif t == 8:
            cases.append(_generated_file_contains_case(index))
        else:
            cases.append(_generated_text_file_case(index))
    return cases


def _load_curated():
    if not CURATED_PATH.exists():
        return []

    with CURATED_PATH.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if isinstance(data, dict):
        data = data.get("tests", [])

    if not isinstance(data, list):
        raise ValueError(f"dataset must be a list: {CURATED_PATH}")

    return data


def _generated_text_file_case(index):
    path = f"generated/text/case_{index:03d}.txt"
    content = f"valor_{index:03d}"
    return _tool_case(
        name=f"real_generated_text_{index:03d}",
        input_text=f"crie arquivo chamado {path} com {content}",
        path=path,
        content=content,
    )


def _generated_nested_file_case(index):
    folder = f"generated/projeto_{index:03d}"
    filename = f"resultado_{index:03d}.txt"
    path = f"{folder}/{filename}"
    content = f"ok_{index:03d}"
    return _tool_case(
        name=f"real_generated_nested_{index:03d}",
        input_text=(
            f"crie uma pasta chamada {folder}, dentro crie arquivo {filename} "
            f"com {content} e depois leia"
        ),
        path=path,
        content=content,
    )


def _generated_csv_case(index):
    left = index + 1
    middle = index + 2
    right = index + 3
    path = f"generated/csv/dados_{index:03d}.csv"
    content = f"{left},{middle},{right}"
    return _tool_case(
        name=f"real_generated_csv_{index:03d}",
        input_text=f"crie arquivo chamado {path} com {content} e depois leia",
        path=path,
        content=content,
    )


def _generated_read_fixture_case(index):
    path = f"fixtures/read_{index:03d}.txt"
    content = f"fixture_{index:03d}"
    return {
        "name": f"real_generated_read_fixture_{index:03d}",
        "type": "real_local",
        "input": f"leia arquivo {path}",
        "expected": content,
        "min_score": 0.75,
        "setup": {"files": {path: content}},
        "verification": [
            {"type": "file_equals", "path": path, "equals": content},
        ],
        "expectations": {
            "requires_tools": True,
            "requires_benchmark_verification": True,
            "verification_must_pass": True,
            "critical_expectations": ["verification_must_pass"],
        },
    }


def _tool_case(name, input_text, path, content):
    expectations = {
        "requires_tools": True,
        "expected_files": [path],
        "expected_file_contents": {path: {"equals": content}},
        "requires_benchmark_verification": True,
        "verification_must_pass": True,
        "critical_expectations": [
            "expected_files",
            "expected_file_contents",
            "verification_must_pass",
        ],
        "process_weights": {
            "requires_tools": 1,
            "expected_files": 2,
            "expected_file_contents": 3,
            "requires_benchmark_verification": 1,
            "verification_must_pass": 3,
        },
    }
    return {
        "name": name,
        "type": "real_local",
        "input": input_text,
        "min_score": 0.75,
        "verification": [
            {"type": "file_equals", "path": path, "equals": content},
        ],
        "expectations": expectations,
    }


def _generated_python_exec_case(index):
    path = f"generated/py/script_{index:03d}.py"
    value = f"py_{index:03d}"
    content = f"print('{value}')\n"
    return {
        "name": f"real_generated_python_{index:03d}",
        "type": "real_local",
        "input": f"leia arquivo {path}",
        "expected": value,
        "min_score": 0.75,
        "setup": {"files": [{"path": path, "content": content}]},
        "verification": [
            {"type": "python_file", "path": path, "stdout_contains": value},
        ],
        "expectations": {
            "requires_tools": True,
            "expected_files": [path],
            "requires_benchmark_verification": True,
            "verification_must_pass": True,
            "critical_expectations": ["expected_files", "verification_must_pass"],
        },
    }


def _generated_python_module_case(index):
    pkg = f"pkg_{index:03d}"
    module_path = f"{pkg}/tool.py"
    module_content = (
        "def main():\n"
        f"    print('module_ok_{index:03d}')\n\n"
        "if __name__ == '__main__':\n"
        "    main()\n"
    )
    return {
        "name": f"real_generated_module_{index:03d}",
        "type": "real_local",
        "input": f"liste arquivos da pasta {pkg}",
        "expected": "tool.py",
        "setup": {
            "dirs": [pkg],
            "files": {f"{pkg}/__init__.py": "", module_path: module_content},
        },
        "verification": [
            {"type": "python_module", "module": f"{pkg}.tool", "stdout_contains": f"module_ok_{index:03d}"}
        ],
        "expectations": {
            "requires_tools": True,
            "requires_benchmark_verification": True,
            "verification_must_pass": True,
        },
    }


def _generated_pytest_case(index):
    test = f"generated/test_calc_{index:03d}.py"
    test_content = "def test_add():\n    assert 2 + 3 == 5\n"
    return {
        "name": f"real_generated_pytest_{index:03d}",
        "type": "real_local",
        "input": f"leia arquivo {test}",
        "expected": "test_add",
        "setup": {"files": {test: test_content}},
        "verification": [
            {"type": "pytest", "path": test, "args": ["-q"], "timeout": 20}
        ],
        "expectations": {
            "requires_tools": True,
            "requires_benchmark_verification": True,
            "verification_must_pass": True,
        },
    }


def _generated_swe_challenge_case(index):
    # Small repo with an initially failing test to serve as a repair challenge.
    module = f"swe/project_{index:03d}/calc.py"
    test = f"swe/project_{index:03d}/test_calc.py"
    # Deliberate bug: test expects wrong result to create a failing baseline
    module_content = "def add(a, b):\n    return a + b\n"
    test_content = "from project_%03d.calc import add\n\ndef test_add():\n    assert add(2, 3) == 6\n" % index
    return {
        "name": f"real_generated_swe_challenge_{index:03d}",
        "type": "real_local",
        "input": "corrija o projeto para que os testes passem",
        "setup": {"dirs": [f"swe/project_{index:03d}"], "files": {module: module_content, test: test_content}},
        "verification": [
            {"type": "pytest", "path": test, "args": ["-q"], "timeout": 20}
        ],
        "expectations": {
            "requires_tools": True,
            "requires_benchmark_verification": True,
            "verification_must_pass": False,
            "critical_expectations": [],
        },
    }


def _generated_file_contains_case(index):
    path = f"generated/contains/case_{index:03d}.txt"
    content = f"line_a_{index:03d}\nline_b_{index:03d}\n"
    return {
        "name": f"real_generated_contains_{index:03d}",
        "type": "real_local",
        "input": f"leia arquivo {path}",
        "expected": f"line_a_{index:03d}",
        "setup": {"files": [{"path": path, "content": content}]},
        "verification": [
            {"type": "file_contains", "path": path, "contains": [f"line_a_{index:03d}", f"line_b_{index:03d}"]}
        ],
        "expectations": {
            "requires_tools": True,
            "requires_benchmark_verification": True,
            "verification_must_pass": True,
        },
    }
