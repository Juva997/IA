import os

from benchmark.process_metrics import compute_process_metrics
from benchmark.runner import BenchmarkRunner, list_dataset_names, load_dataset, write_json_report
from benchmark.validators.process import (
    compute_efficiency_factor,
    process_check,
    validate_process,
)


def test_runner_repeat_aggregates_runs(tmp_path):
    class FakeEngine:
        def __init__(self):
            self.calls = 0

        def run(self, text):
            self.calls += 1
            return {"status": "success", "output": "ok"}

    runner = BenchmarkRunner(
        engine=FakeEngine(),
        dataset=[{"name": "repeat", "input": "x", "type": "qa", "expected": "ok"}],
        runs=2,
        workspace_dir=str(tmp_path),
    )

    results = runner.run()

    assert len(results) == 1
    assert results[0]["status"] == "success"
    assert results[0]["metrics"]["runs"] == 2
    assert len(results[0]["runs"]) == 2


def test_load_dataset_all_includes_default_datasets():
    names = {test["name"] for test in load_dataset("all")}

    assert "equacao_simples" in names
    assert "prompt_injection_delete_escape" in names
    assert "memoria_nome" in names
    assert "real_file_create_exact" not in names
    assert "mini_swe_proj_001_fix_add" not in names


def test_load_dataset_full_includes_smoke_and_large_datasets():
    names = {test["name"] for test in load_dataset("full")}

    assert "equacao_simples" in names
    assert "real_file_create_exact" in names
    assert "mini_swe_proj_001_fix_add" in names


def test_load_dataset_optional_includes_llm_slow_and_e2e_only_on_request():
    optional_names = {test["name"] for test in load_dataset("optional")}
    smoke_names = {test["name"] for test in load_dataset("all")}

    assert len(optional_names) >= 30
    assert "llm_offline_chat_greeting" in optional_names
    assert "slow_python_script_numbers" in optional_names
    assert "e2e_optional_resolucao_problemas" in optional_names
    assert optional_names.isdisjoint(smoke_names)


def test_load_dataset_legacy_optional_aliases_stay_offline():
    assert load_dataset("llm_external")[0]["name"].startswith("llm_offline_")
    assert load_dataset("slow_optional")[0]["name"].startswith("slow_")


def test_load_dataset_prefers_builtin_name_over_same_named_directory():
    names = {test["name"] for test in load_dataset("memory")}

    assert "memoria_nome" in names


def test_runner_filters_external_llm_cases_unless_enabled(tmp_path):
    class FakeEngine:
        def run(self, text):
            return {"status": "success", "output": "ok"}

    dataset = [
        {
            "name": "external",
            "input": "x",
            "type": "qa",
            "expected": "ok",
            "requires_external_llm": True,
        }
    ]

    offline_runner = BenchmarkRunner(
        engine=FakeEngine(),
        dataset=dataset,
        runs=1,
        workspace_dir=str(tmp_path),
    )
    external_runner = BenchmarkRunner(
        engine=FakeEngine(),
        dataset=dataset,
        runs=1,
        workspace_dir=str(tmp_path),
        use_external_llm=True,
    )

    assert offline_runner.run() == []
    assert external_runner.run()[0]["status"] == "success"


def test_write_json_report(tmp_path):
    report_path = tmp_path / "report.json"
    results = [{"name": "ok", "status": "success", "metrics": {"final_score": 1.0}}]

    written = write_json_report(
        results, report_path, meta={"dataset": "unit", "runs_per_test": 3}
    )

    assert written == str(report_path)
    assert report_path.exists()
    text = report_path.read_text(encoding="utf-8")
    assert '"quality_gate": "PRODUCTION READY"' in text
    assert '"meta"' in text
    assert '"dataset": "unit"' in text
    assert '"generated_at"' in text


def test_list_dataset_names_covers_json_stems():
    names = list_dataset_names()
    assert "reasoning" in names
    assert "formatting" in names
    assert "full" in names
    assert "optional" in names


def test_runner_uses_workspace_dir(tmp_path):
    roots = []

    class FakeEngine:
        def run(self, text):
            roots.append(os.getcwd())
            return {"status": "success", "output": "ok"}

    runner = BenchmarkRunner(
        engine=FakeEngine(),
        dataset=[{"name": "workspace", "input": "x", "type": "qa", "expected": "ok"}],
        runs=1,
        workspace_dir=str(tmp_path),
    )
    results = runner.run()

    assert results[0]["status"] == "success"
    assert roots
    assert os.path.commonpath([roots[0], str(tmp_path)]) == str(tmp_path)


def test_runner_adds_process_metrics_from_agent_trace(tmp_path):
    class FakeEngine:
        def run(self, text):
            return {
                "status": "success",
                "output": "ok",
                "iterations": 2,
                "attempts": [
                    {"status": "error", "output": "bad"},
                    {"status": "success", "output": "ok"},
                ],
                "trace": {
                    "steps": 2,
                    "failures": 1,
                    "timeline": [
                        {"event": "critique"},
                        {"event": "step", "action": "run_python"},
                        {"event": "verify"},
                    ],
                },
            }

    runner = BenchmarkRunner(
        engine=FakeEngine(),
        dataset=[
            {
                "name": "process",
                "input": "x",
                "type": "agent",
                "expected": "ok",
                "expectations": {
                    "requires_trace": True,
                    "requires_tools": True,
                    "requires_critic": True,
                    "requires_verification": True,
                    "min_iterations": 2,
                },
            }
        ],
        runs=1,
        workspace_dir=str(tmp_path),
    )

    result = runner.run()[0]

    assert result["status"] == "success"
    assert result["evaluation"]["process"] == 1.0
    assert result["metrics"]["process"]["has_trace"] is True
    assert result["metrics"]["process"]["failure_recovery"] is True
    assert result["metrics"]["agent_score"] >= result["metrics"]["final_score"]


def test_runner_enforces_process_expectations(tmp_path):
    class FakeEngine:
        def run(self, text):
            return {"status": "success", "output": "ok"}

    runner = BenchmarkRunner(
        engine=FakeEngine(),
        dataset=[
            {
                "name": "missing_trace",
                "input": "x",
                "type": "agent",
                "expected": "ok",
                "expectations": {"requires_trace": True},
            }
        ],
        runs=1,
        workspace_dir=str(tmp_path),
    )

    result = runner.run()[0]

    assert result["status"] == "error"
    assert result["evaluation"]["process"] == 0.0


def test_runner_validates_workspace_file_contents_with_weights(tmp_path):
    class FakeEngine:
        def run(self, text):
            os.makedirs("out", exist_ok=True)
            with open("out/result.txt", "w", encoding="utf-8") as file:
                file.write("ok")
            return {"status": "success", "output": "ok"}

    runner = BenchmarkRunner(
        engine=FakeEngine(),
        dataset=[
            {
                "name": "artifact",
                "input": "x",
                "type": "tool",
                "expected": "ok",
                "expectations": {
                    "requires_tools": True,
                    "expected_files": ["out/result.txt"],
                    "expected_file_contents": {"out/result.txt": {"equals": "ok"}},
                    "process_weights": {
                        "requires_tools": 1,
                        "expected_files": 2,
                        "expected_file_contents": 3,
                    },
                    "critical_expectations": ["expected_file_contents"],
                },
            }
        ],
        runs=1,
        workspace_dir=str(tmp_path),
    )

    result = runner.run()[0]

    assert result["status"] == "success"
    assert result["evaluation"]["process"] == 1.0
    assert result["metrics"]["process"]["workspace_artifacts"]["out/result.txt"]["text"] == "ok"


def test_runner_critical_process_expectation_forces_zero_score(tmp_path):
    class FakeEngine:
        def run(self, text):
            os.makedirs("out", exist_ok=True)
            with open("out/result.txt", "w", encoding="utf-8") as file:
                file.write("wrong")
            return {"status": "success", "output": "ok"}

    runner = BenchmarkRunner(
        engine=FakeEngine(),
        dataset=[
            {
                "name": "artifact_bad",
                "input": "x",
                "type": "tool",
                "expected": "ok",
                "expectations": {
                    "expected_file_contents": {"out/result.txt": {"equals": "ok"}},
                    "critical_expectations": ["expected_file_contents"],
                },
            }
        ],
        runs=1,
        workspace_dir=str(tmp_path),
    )

    result = runner.run()[0]

    assert result["status"] == "error"
    assert result["evaluation"]["process"] == 0.0


def test_iteration_semantic_delta_between_attempts():
    outputs = [
        {
            "status": "success",
            "output": "final",
            "raw": {
                "attempts": [
                    {"output": "alpha beta"},
                    {"output": "alpha beta gamma"},
                ],
            },
        }
    ]
    metrics = compute_process_metrics(outputs)

    assert metrics["iteration_semantic_runs_with_pairs"] == 1
    assert metrics["iteration_semantic_delta_avg"] > 0
    assert metrics["iteration_semantic_first_last_distance"] > 0


def _synthetic_process(**overrides):
    base = {
        "tool_sequence": [],
        "tools": [],
        "tool_calls": 0,
        "steps": 0,
        "agent_steps": 0,
        "benchmark_steps": 0,
        "workspace_files": [],
        "workspace_artifacts": {},
        "workspace_writes": 0,
        "has_trace": False,
        "has_refinement": False,
        "has_critic": False,
        "has_verification": False,
        "failure_recovery": False,
        "improvement_gain": 0,
        "initial_score_avg": 0,
        "final_score_avg": 0,
        "iterations_avg": 0,
        "attempts_avg": 0,
        "stability_score": 1.0,
        "semantic_stability_score": 1.0,
        "iteration_semantic_delta_avg": 0.0,
        "iteration_semantic_first_last_distance": 0.0,
        "iteration_semantic_runs_with_pairs": 0,
        "redundant_tool_calls": 0,
        "efficiency_factor": 1.0,
    }
    base.update(overrides)
    return base


def test_tool_dependencies_and_exact_sequence_validate_process():
    proc_ok = _synthetic_process(
        tool_sequence=["list_dir", "read_file", "write_file"],
        tools=["list_dir", "read_file", "write_file"],
        tool_calls=3,
        steps=3,
    )
    exp_dep = {
        "tool_dependencies": [["list_dir", "write_file"], ["read_file", "write_file"]],
    }
    assert validate_process(proc_ok, exp_dep) is True

    proc_bad = dict(proc_ok)
    proc_bad["tool_sequence"] = ["write_file", "list_dir"]
    proc_bad["tool_calls"] = 2
    assert validate_process(proc_bad, exp_dep) is False

    proc_exact_ok = _synthetic_process(tool_sequence=["a", "b"], tools=["a", "b"], tool_calls=2)
    assert validate_process(proc_exact_ok, {"exact_tool_sequence": ["a", "b"]}) is True

    proc_exact_bad = dict(proc_exact_ok)
    proc_exact_bad["tool_sequence"] = ["a", "c"]
    assert validate_process(proc_exact_bad, {"exact_tool_sequence": ["a", "b"]}) is False


def test_max_tool_calls_expectation_process_check():
    assert (
        process_check({"expectations": {"max_tool_calls": 5}}, [{}]) == 1.0
    )

    proc = _synthetic_process(tool_sequence=["x", "x"], tools=["x"], tool_calls=2, steps=2, redundant_tool_calls=1)
    test = {"expectations": {"max_tool_calls": 1, "critical_expectations": ["max_tool_calls"]}}
    assert validate_process(proc, test["expectations"]) is False


def test_efficiency_budget_penalty_on_agent_score():
    from benchmark.metrics import compute_agent_score, compute_metrics

    base_metrics = {
        "runs": 1,
        "latency_avg": 0.1,
        "latency_stdev": 0.0,
        "latency_p50": 0.1,
        "latency_p95": 0.1,
        "latency_p99": 0.1,
        "latency_min": 0.1,
        "latency_max": 0.1,
        "semantic_score": 1.0,
        "format_score": 1.0,
        "consistency_score": 1.0,
        "status_score": 1.0,
        "process_score": 1.0,
        "final_score": 1.0,
        "process": {"efficiency_factor": 1.0},
    }

    penalized = dict(base_metrics)
    penalized["process"] = {"efficiency_factor": 0.5}

    assert compute_agent_score(base_metrics) > compute_agent_score(penalized)

    expectations = {"efficiency_budget": {"tool_calls": 10}}
    proc_over = {"tool_calls": 20, "steps": 5, "agent_steps": 0, "benchmark_steps": 0}
    assert compute_efficiency_factor(expectations, proc_over) == 0.5

    full = compute_metrics(
        [{"status": "success", "output": "ok"}],
        [0.1],
        {
            "semantic": 1.0,
            "format": 1.0,
            "consistency": 1.0,
            "status": 1.0,
            "process": 1.0,
        },
        process_metrics={**proc_over, "efficiency_factor": 0.5},
    )
    assert full["agent_score"] < 1.0


def test_runner_applies_efficiency_budget(tmp_path):
    class FakeEngine:
        def run(self, text):
            return {"status": "success", "output": "ok"}

    runner = BenchmarkRunner(
        engine=FakeEngine(),
        dataset=[
            {
                "name": "eff",
                "input": "x",
                "type": "qa",
                "expected": "ok",
                "expectations": {"efficiency_budget": {"steps": 1}},
            }
        ],
        runs=1,
        workspace_dir=str(tmp_path),
    )
    result = runner.run()[0]

    assert result["metrics"]["process"]["efficiency_factor"] == 1.0


def test_min_iteration_semantic_delta_skipped_when_single_attempt(tmp_path):
    class FakeEngine:
        def run(self, text):
            return {"status": "success", "output": "only"}

    runner = BenchmarkRunner(
        engine=FakeEngine(),
        dataset=[
            {
                "name": "sem_delta",
                "input": "x",
                "type": "agent",
                "expected": "only",
                "expectations": {"min_iteration_semantic_delta": 0.5},
            }
        ],
        runs=1,
        workspace_dir=str(tmp_path),
    )
    assert runner.run()[0]["status"] == "success"
