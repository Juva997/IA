from benchmark.metrics import (
    compute_agent_score,
    compute_learning_metrics,
    compute_metrics,
    quality_gate,
)
from benchmark.process_metrics import compute_process_metrics, compute_stability


def test_compute_metrics_includes_percentiles():
    evaluation = {
        "semantic": 1.0,
        "format": 1.0,
        "consistency": 1.0,
        "status": 1.0,
    }

    metrics = compute_metrics(
        outputs=[{"output": "ok"} for _ in range(5)],
        times=[0.1, 0.2, 0.3, 0.4, 0.5],
        evaluation=evaluation,
    )

    assert metrics["runs"] == 5
    assert metrics["latency_avg"] == 0.3
    assert metrics["latency_stdev"] > 0
    assert metrics["latency_p95"] >= metrics["latency_p50"]
    assert metrics["process_score"] == 1.0
    assert metrics["final_score"] == 1.0


def test_quality_gate_statuses():
    production = [{"metrics": {"final_score": 0.95}}]
    staging = [{"metrics": {"final_score": 0.8}}]
    failed = [{"metrics": {"final_score": 0.5}}]

    assert quality_gate(production) == "PRODUCTION READY"
    assert quality_gate(staging) == "STAGING"
    assert quality_gate(failed) == "FAIL"
    assert quality_gate([]) == "FAIL"


def test_compute_learning_metrics_tracks_v7_signals():
    metrics = compute_learning_metrics(
        [
            {"score": 0.4, "passed": False, "attempts": 3, "used_experiences": 0},
            {"score": 0.9, "passed": True, "attempts": 1, "used_experiences": 2},
        ]
    )

    assert metrics["learning_rate"] > 0
    assert metrics["success_trend"] > 0
    assert metrics["retry_efficiency"] == 0.5
    assert metrics["knowledge_reuse"] == 0.5


def test_process_metrics_extract_agent_trace_and_stability():
    outputs = [
        {
            "status": "success",
            "output": "ok",
            "trace": {
                "steps": 1,
                "failures": 0,
                "timeline": [{"event": "step", "action": "write_file"}],
            },
            "raw": {"status": "success", "iterations": 1},
        },
        {
            "status": "success",
            "output": "ok",
            "trace": {
                "steps": 1,
                "failures": 0,
                "timeline": [{"event": "step", "action": "write_file"}],
            },
            "raw": {"status": "success", "iterations": 1},
        },
    ]

    process = compute_process_metrics(outputs)

    assert process["has_trace"] is True
    assert process["agent_steps"] == 2
    assert process["tool_calls"] == 2
    assert process["tools"] == ["write_file"]
    assert process["tool_sequence"] == ["write_file", "write_file"]
    assert process["stability_score"] == 1.0
    assert process["semantic_stability_score"] == 1.0
    assert compute_stability(outputs) == 1.0


def test_process_metrics_tracks_iteration_gain():
    process = compute_process_metrics(
        [
            {
                "status": "success",
                "output": "ok",
                "raw": {
                    "status": "success",
                    "attempts": [
                        {"status": "error", "score": 0.2},
                        {"status": "success", "score": 0.9},
                    ],
                },
            }
        ]
    )

    assert process["initial_score_avg"] == 0.2
    assert process["final_score_avg"] == 0.9
    assert process["improvement_gain"] == 0.7


def test_compute_agent_score_keeps_final_score_separate():
    metrics = {
        "semantic_score": 1.0,
        "consistency_score": 1.0,
        "process_score": 1.0,
        "process": {"tool_calls": 1, "has_refinement": True},
    }

    assert compute_agent_score(metrics) == 1.0
