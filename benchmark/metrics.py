import statistics


def compute_metrics(outputs, times, evaluation, weights=None, process_metrics=None):
    weights = weights or _default_weights(evaluation)
    total_weight = sum(weights.values()) or 1.0

    final_score = sum(
        float(evaluation.get(name, 0.0)) * weight
        for name, weight in weights.items()
    ) / total_weight

    metrics = {
        "runs": len(outputs),
        "latency_avg": _mean(times),
        "latency_stdev": _stdev(times),
        "latency_p50": _percentile(times, 50),
        "latency_p95": _percentile(times, 95),
        "latency_p99": _percentile(times, 99),
        "latency_min": min(times) if times else 0.0,
        "latency_max": max(times) if times else 0.0,
        "semantic_score": float(evaluation.get("semantic", 0.0)),
        "format_score": float(evaluation.get("format", 0.0)),
        "consistency_score": float(evaluation.get("consistency", 0.0)),
        "status_score": float(evaluation.get("status", 0.0)),
        "process_score": float(evaluation.get("process", 1.0)),
        "final_score": round(final_score, 4),
        "process": process_metrics or {},
    }
    if "rubric" in evaluation:
        metrics["rubric_score"] = float(evaluation.get("rubric", 0.0))
    if "judge" in evaluation:
        metrics["judge_score"] = float(evaluation.get("judge", 0.0))
    metrics["agent_score"] = compute_agent_score(metrics)
    return metrics


def _default_weights(evaluation):
    if "rubric" in evaluation and "judge" in evaluation:
        return {
            "semantic": 0.20,
            "format": 0.10,
            "consistency": 0.10,
            "status": 0.10,
            "rubric": 0.30,
            "judge": 0.20,
        }

    if "rubric" in evaluation:
        return {
            "semantic": 0.30,
            "format": 0.15,
            "consistency": 0.15,
            "status": 0.10,
            "rubric": 0.30,
        }

    if "judge" in evaluation:
        return {
            "semantic": 0.25,
            "format": 0.15,
            "consistency": 0.15,
            "status": 0.10,
            "judge": 0.35,
        }

    return {
        "semantic": 0.45,
        "format": 0.20,
        "consistency": 0.20,
        "status": 0.15,
    }


def compute_agent_score(metrics):
    process = metrics.get("process", {}) or {}
    tool_score = 1.0 if int(process.get("tool_calls", 0) or 0) > 0 else 0.0
    if int(process.get("workspace_writes", 0) or 0) > 0:
        tool_score = 1.0

    refinement_score = 1.0 if process.get("has_refinement") else 0.0
    stability_score = float(
        process.get("semantic_stability_score", process.get("stability_score", 1.0))
    )
    improvement_score = _improvement_score(process)
    efficiency_factor = float(process.get("efficiency_factor", 1.0))

    score = (
        float(metrics.get("semantic_score", 0.0)) * 0.35
        + float(metrics.get("consistency_score", 0.0)) * 0.15
        + float(metrics.get("process_score", 1.0)) * 0.25
        + tool_score * 0.1
        + refinement_score * 0.05
        + stability_score * 0.05
        + improvement_score * 0.05
    )
    return round(max(0.0, min(1.0, score * efficiency_factor)), 4)


def quality_gate(results, production_score=0.90, staging_score=0.75):
    if not results:
        return "FAIL"

    avg_score = sum(
        result.get("metrics", {}).get("final_score", 0.0)
        for result in results
    ) / len(results)

    if avg_score >= production_score:
        return "PRODUCTION READY"
    if avg_score >= staging_score:
        return "STAGING"
    return "FAIL"


def compute_learning_metrics(history):
    history = list(history or [])
    if not history:
        return {
            "learning_rate": 0.0,
            "success_trend": 0.0,
            "retry_efficiency": 0.0,
            "knowledge_reuse": 0.0,
        }

    scores = [float(item.get("score", 0.0)) for item in history]
    midpoint = max(1, len(scores) // 2)
    early = scores[:midpoint]
    late = scores[midpoint:] or scores

    early_success = _success_rate(history[:midpoint])
    late_success = _success_rate(history[midpoint:] or history)
    attempts = [int(item.get("attempts", 1) or 1) for item in history]
    reused = [
        item
        for item in history
        if int(item.get("used_experiences", 0) or 0) > 0
        or int(item.get("metadata", {}).get("used_experiences", 0) or 0) > 0
    ]

    return {
        "learning_rate": round(_mean(late) - _mean(early), 4),
        "success_trend": round(late_success - early_success, 4),
        "retry_efficiency": round(1.0 / max(1.0, _mean(attempts)), 4),
        "knowledge_reuse": round(len(reused) / len(history), 4),
    }


def _mean(values):
    return sum(values) / len(values) if values else 0.0


def _stdev(values):
    values = [float(x) for x in (values or [])]
    if len(values) < 2:
        return 0.0
    return round(statistics.stdev(values), 6)


def _improvement_score(process):
    if "improvement_gain" not in process:
        return 1.0

    if not process.get("has_refinement") and float(process.get("attempts_avg", 0.0)) <= 1:
        return 1.0

    gain = float(process.get("improvement_gain", 0.0))
    return max(0.0, min(1.0, 0.5 + gain))


def _success_rate(history):
    if not history:
        return 0.0
    return sum(1 for item in history if _passed(item)) / len(history)


def _passed(item):
    if "passed" in item:
        return bool(item.get("passed"))
    status = str(item.get("status", "")).lower()
    return status == "success" or float(item.get("score", 0.0)) >= 0.9


def _percentile(values, percentile):
    if not values:
        return 0.0

    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]

    rank = (len(ordered) - 1) * (percentile / 100)
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight
