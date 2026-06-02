import os

from benchmark.evaluator import evaluate
from benchmark.metrics import compute_metrics, quality_gate
from benchmark.runner import BenchmarkRunner, load_dataset
from benchmark.validators.consistency import consistency_check
from benchmark.validators.format import format_check
from benchmark.validators.semantic import semantic_check


def test_semantic_math_accepts_engine_dict_output():
    test = {"name": "math", "type": "math", "expected": 3}
    outputs = [{"status": "success", "output": "x = 3"}]

    assert semantic_check(test, outputs) == 1.0


def test_format_check_json_uses_output_field():
    test = {"name": "json", "type": "format", "format": "json"}
    outputs = [{"status": "success", "output": '{"nome": "Joao", "idade": 20}'}]

    assert format_check(test, outputs) == 1.0


def test_consistency_allows_majority_score():
    outputs = [
        {"status": "success", "output": "ok"},
        {"status": "success", "output": "ok"},
        {"status": "success", "output": "OK diferente"},
    ]

    assert consistency_check(outputs) == 2 / 3


def test_metrics_and_quality_gate():
    evaluation = {
        "semantic": 1.0,
        "format": 1.0,
        "consistency": 1.0,
        "status": 1.0,
    }
    metrics = compute_metrics([{"output": "ok"}], [0.01], evaluation)
    results = [{"metrics": metrics, "status": "success"}]

    assert metrics["final_score"] == 1.0
    assert quality_gate(results) == "PRODUCTION READY"


def test_evaluate_supports_semantic_expectation_and_rubric():
    test = {
        "name": "quality",
        "type": "qa",
        "expected": "backtracking",
        "semantic_expectation": {
            "must_contain_concepts": ["backtracking", ["coluna", "diagonal"]],
            "must_not_contain_concepts": ["forca bruta sem poda"],
        },
        "rubric": {
            "criteria": {
                "accuracy": {"weight": 2, "must_contain": ["backtracking"]},
                "coverage": {"weight": 1, "must_contain_any": [["coluna", "diagonal"]]},
            }
        },
    }
    outputs = [
        {
            "status": "success",
            "output": "Use backtracking, evitando conflitos em coluna e diagonal.",
        }
    ]

    evaluation = evaluate(test, outputs)
    metrics = compute_metrics(outputs, [0.01], evaluation)

    assert evaluation["rubric"] == 1.0
    assert metrics["rubric_score"] == 1.0
    assert metrics["final_score"] == 1.0


def test_semantic_expectation_penalizes_missing_required_concepts():
    test = {
        "name": "quality_missing",
        "type": "qa",
        "expected": "ok",
        "semantic_expectation": {
            "must_contain_concepts": ["causa raiz"],
        },
    }
    outputs = [{"status": "success", "output": "ok"}]

    evaluation = evaluate(test, outputs)

    assert evaluation["semantic"] == 0.5
    assert evaluation["semantic_detail"]["runs"][0]["legacy_score"] == 1.0
    assert evaluation["semantic_detail"]["runs"][0]["expectation_score"] == 0.0


def test_evaluate_uses_workspace_artifacts_for_quality_checks():
    test = {
        "name": "artifact_quality",
        "type": "real_local",
        "semantic_expectation": {
            "must_contain_concepts": ["time.perf_counter", "def benchmark"],
        },
        "rubric": {
            "criteria": {
                "measures_time": {"must_contain": ["time.perf_counter"]},
                "has_entrypoint": {"must_contain": ["def benchmark"]},
            }
        },
    }
    outputs = [
        {
            "status": "success",
            "output": "arquivo criado",
            "workspace_artifacts": {
                "benchmark_exemplo.py": {
                    "text": "import time\n\ndef benchmark():\n    return time.perf_counter()\n",
                }
            },
        }
    ]

    evaluation = evaluate(test, outputs)

    assert evaluation["semantic"] == 1.0
    assert evaluation["rubric"] == 1.0
    assert evaluation["rubric_detail"]["runs"][0]["criteria"][0]["score"] == 1.0


def test_rubric_must_contain_any_accepts_flat_option_list():
    test = {
        "name": "any",
        "type": "qa",
        "rubric": {
            "criteria": {
                "usefulness": {
                    "must_contain_any": ["diagnosticar", "rastrear", "corrigir"]
                }
            }
        },
    }
    outputs = [{"status": "success", "output": "Logs ajudam a rastrear falhas."}]

    evaluation = evaluate(test, outputs)

    assert evaluation["rubric"] == 1.0
    assert evaluation["rubric_detail"]["runs"][0]["criteria"][0]["checks"][0]["passed"]


def test_evaluate_supports_injected_llm_judge():
    class FakeJudge:
        def __init__(self):
            self.calls = []

        def generate(self, *args):
            self.calls.append(args)
            return '{"score": 0.8, "accuracy": 0.8}'

    judge = FakeJudge()
    test = {
        "name": "judge",
        "type": "qa",
        "input": "explique x",
        "expected": "ok",
        "llm_judge": True,
        "min_judge_score": 0.7,
    }
    outputs = [{"status": "success", "output": "ok"}]

    evaluation = evaluate(test, outputs, llm_judge=judge)
    metrics = compute_metrics(outputs, [0.01], evaluation)

    assert evaluation["judge"] == 0.8
    assert metrics["judge_score"] == 0.8
    assert judge.calls


def test_llm_judge_uses_dimension_scores_when_score_is_incoherent():
    class FakeJudge:
        def generate(self, *args):
            return (
                '{"score": 0.2, "accuracy": 0.8, "completeness": 0.6, '
                '"instruction_following": 1.0, "reasoning": 0.6}'
            )

    test = {
        "name": "judge_dimensions",
        "type": "qa",
        "input": "explique x",
        "llm_judge": True,
    }
    outputs = [{"status": "success", "output": "ok"}]

    evaluation = evaluate(test, outputs, llm_judge=FakeJudge())

    assert evaluation["judge"] == 0.75


def test_runner_enforces_min_rubric_score(tmp_path):
    class FakeEngine:
        def run(self, text):
            return {"status": "success", "output": "resposta rasa"}

    runner = BenchmarkRunner(
        engine=FakeEngine(),
        dataset=[
            {
                "name": "rubric_bad",
                "input": "x",
                "type": "qa",
                "expected": "resposta",
                "min_rubric_score": 0.9,
                "rubric": {
                    "criteria": {
                        "missing": {"must_contain": ["conceito ausente"]},
                    }
                },
            }
        ],
        runs=1,
        workspace_dir=str(tmp_path),
    )

    result = runner.run()[0]

    assert result["status"] == "error"
    assert result["evaluation"]["rubric"] == 0.0


def test_runner_supports_sequence_and_workspace_isolation(tmp_path):
    roots = []

    class FakeEngine:
        def __init__(self, root):
            self.root = root
            self.name = None

        def run(self, text):
            roots.append(os.getcwd())
            if "Meu nome" in text:
                self.name = text.rsplit(" ", 1)[-1]
                return {"status": "success", "output": f"Entendido: {self.name}"}
            return {"status": "success", "output": f"Seu nome e {self.name}"}

    dataset = [
        {
            "name": "memoria_fake",
            "type": "memory",
            "steps": [
                {"input": "Meu nome e Carlos", "expected": "Carlos", "type": "memory"},
                {"input": "Qual e meu nome?", "expected": "Carlos", "type": "qa"},
            ],
        }
    ]

    runner = BenchmarkRunner(
        engine_factory=FakeEngine,
        dataset=dataset,
        runs=1,
        workspace_dir=str(tmp_path),
        include_runs=True,
    )
    results = runner.run()

    assert results[0]["status"] == "success"
    assert results[0]["metrics"]["semantic_score"] == 1.0
    assert roots
    for root in roots:
        assert os.path.commonpath([root, str(tmp_path)]) == str(tmp_path)


def test_runner_enforces_required_format_dimension(tmp_path):
    class FakeEngine:
        def __init__(self, root):
            self.root = root

        def run(self, text):
            return {"status": "success", "output": "nao e json"}

    dataset = [
        {
            "name": "json_ruim",
            "type": "format",
            "input": "json",
            "format": "json",
        }
    ]

    runner = BenchmarkRunner(
        engine_factory=FakeEngine,
        dataset=dataset,
        runs=1,
        workspace_dir=str(tmp_path),
    )
    results = runner.run()

    assert results[0]["status"] == "error"
    assert results[0]["evaluation"]["format"] == 0.0


def test_evaluate_marks_error_status():
    test = {"name": "erro", "type": "qa", "expected": "ok"}
    outputs = [{"status": "error", "output": "falha", "error": "falha"}]

    evaluation = evaluate(test, outputs)

    assert evaluation["status"] == 0.0
    assert evaluation["semantic"] == 0.0


def test_load_dataset_by_name():
    dataset = load_dataset("reasoning")

    assert any(test["name"] == "equacao_simples" for test in dataset)
