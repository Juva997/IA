from benchmark.validators.common import normalized_text


def compute_process_metrics(outputs):
    outputs = list(outputs or [])
    traces = [_extract_trace(output) for output in outputs]
    raw_outputs = [_raw(output) for output in outputs]

    agent_steps = sum(_agent_steps(output, trace) for output, trace in zip(raw_outputs, traces))
    benchmark_steps = sum(_benchmark_steps(output) for output in outputs)
    tool_sequence = _tool_sequence(raw_outputs, traces)
    tools = sorted(set(tool for tool in tool_sequence if tool))
    iterations = [_iterations(output) for output in raw_outputs]
    attempts = [_attempt_count(output) for output in raw_outputs]
    improvement = _improvement_metrics(raw_outputs)
    iteration_semantic = _iteration_semantic_metrics(raw_outputs)
    workspace_files = sorted(
        {
            file
            for output in outputs
            for file in output.get("workspace_files", [])
            if isinstance(output, dict)
        }
    )
    artifacts = _workspace_artifacts(outputs)
    verification = _verification_metrics(outputs)
    setup = _setup_metrics(outputs)

    return {
        "has_trace": any(bool(trace) for trace in traces),
        "agent_steps": agent_steps,
        "benchmark_steps": benchmark_steps,
        "steps": agent_steps or benchmark_steps,
        "tool_calls": len(tool_sequence),
        "tools": tools,
        "tool_sequence": tool_sequence,
        "iterations_avg": _mean([value for value in iterations if value is not None]),
        "attempts_avg": _mean([value for value in attempts if value is not None]),
        "initial_score_avg": improvement["initial_score_avg"],
        "final_score_avg": improvement["final_score_avg"],
        "improvement_gain": improvement["improvement_gain"],
        "refinement_gain": improvement["improvement_gain"],
        "has_refinement": any(_has_refinement(output, trace) for output, trace in zip(raw_outputs, traces)),
        "has_critic": any(_has_key_or_event(output, trace, "critique") for output, trace in zip(raw_outputs, traces)),
        "has_verification": any(_has_key_or_event(output, trace, "verify") for output, trace in zip(raw_outputs, traces)),
        "failure_recovery": any(_failure_recovery(output, trace) for output, trace in zip(raw_outputs, traces)),
        "workspace_files": workspace_files,
        "workspace_artifacts": artifacts,
        "workspace_writes": len([file for file in workspace_files if file != "config.json"]),
        "setup_total": setup["total"],
        "setup_files": setup["files"],
        "setup_dirs": setup["dirs"],
        "verification_total": verification["total"],
        "verification_passed": verification["passed"],
        "verification_failed": verification["failed"],
        "verification_critical_failed": verification["critical_failed"],
        "verification_ok": verification["ok"],
        "stability_score": compute_stability(outputs),
        "semantic_stability_score": compute_semantic_stability(outputs),
        "iteration_semantic_delta_avg": iteration_semantic["delta_avg"],
        "iteration_semantic_first_last_distance": iteration_semantic[
            "first_last_distance"
        ],
        "iteration_semantic_runs_with_pairs": iteration_semantic["runs_with_pairs"],
        "redundant_tool_calls": _redundant_consecutive_calls(tool_sequence),
        "efficiency_factor": 1.0,
    }


def compute_stability(outputs):
    outputs = list(outputs or [])
    if len(outputs) <= 1:
        return 1.0

    texts = [normalized_text(output) for output in outputs]
    unique = len(set(texts))
    return round(1.0 - ((unique - 1) / max(1, len(texts) - 1)), 4)


def compute_semantic_stability(outputs):
    outputs = list(outputs or [])
    if len(outputs) <= 1:
        return 1.0

    token_sets = [_tokens(normalized_text(output)) for output in outputs]
    scores = []
    for left_index, left in enumerate(token_sets):
        for right in token_sets[left_index + 1 :]:
            scores.append(_jaccard(left, right))

    return round(_mean(scores), 4)


def _extract_trace(output):
    raw = _raw(output)
    if isinstance(output, dict) and isinstance(output.get("trace"), dict):
        return output["trace"]
    if isinstance(raw, dict) and isinstance(raw.get("trace"), dict):
        return raw["trace"]
    return {}


def _raw(output):
    if isinstance(output, dict):
        return output.get("raw", output)
    return output


def _agent_steps(raw, trace):
    if isinstance(trace, dict) and isinstance(trace.get("steps"), int):
        return trace["steps"]

    if isinstance(raw, dict) and isinstance(raw.get("steps"), list):
        return len(raw["steps"])

    return 0


def _benchmark_steps(output):
    if isinstance(output, dict) and isinstance(output.get("steps"), list):
        return len(output["steps"])
    return 0


def _tool_sequence(raw_outputs, traces):
    tools = []
    for raw, trace in zip(raw_outputs, traces):
        tools.extend(_tools_from_trace(trace))
        tools.extend(_tools_from_raw(raw))
    return [tool for tool in tools if tool]


def _tools_from_trace(trace):
    timeline = trace.get("timeline", []) if isinstance(trace, dict) else []
    return [
        event.get("action")
        for event in timeline
        if isinstance(event, dict) and event.get("event") == "step"
    ]


def _tools_from_raw(raw):
    if not isinstance(raw, dict):
        return []

    tools = []
    for record in raw.get("steps", []) if isinstance(raw.get("steps"), list) else []:
        step = record.get("step", {}) if isinstance(record, dict) else {}
        if isinstance(step, dict):
            tools.append(step.get("action"))
    return tools


def _iterations(raw):
    if isinstance(raw, dict) and raw.get("iterations") is not None:
        try:
            return float(raw["iterations"])
        except (TypeError, ValueError):
            return None
    return None


def _attempt_count(raw):
    if isinstance(raw, dict) and isinstance(raw.get("attempts"), list):
        return float(len(raw["attempts"]))
    return _iterations(raw)


def _improvement_metrics(raw_outputs):
    initial_scores = []
    final_scores = []
    gains = []

    for raw in raw_outputs:
        scores = _attempt_scores(raw)
        if len(scores) < 2:
            continue
        initial = scores[0]
        final = scores[-1]
        initial_scores.append(initial)
        final_scores.append(final)
        gains.append(final - initial)

    return {
        "initial_score_avg": _mean(initial_scores),
        "final_score_avg": _mean(final_scores),
        "improvement_gain": _mean(gains),
    }


def _attempt_texts_normalized(raw):
    if not isinstance(raw, dict) or not isinstance(raw.get("attempts"), list):
        return []

    texts = []
    for attempt in raw["attempts"]:
        if not isinstance(attempt, dict):
            continue
        fragment = attempt.get("output")
        if fragment is None:
            fragment = attempt.get("text") or attempt.get("content")
        texts.append(" ".join(str(fragment or "").strip().lower().split()))
    return texts


def _iteration_semantic_metrics(raw_outputs):
    deltas = []
    first_last = []
    runs_with_pairs = 0

    for raw in raw_outputs:
        texts = _attempt_texts_normalized(raw)
        if len(texts) < 2:
            continue
        runs_with_pairs += 1
        pair_deltas = []
        for left_index in range(len(texts) - 1):
            ja = _jaccard(_tokens(texts[left_index]), _tokens(texts[left_index + 1]))
            pair_deltas.append(1.0 - ja)
        if pair_deltas:
            deltas.append(_mean(pair_deltas))
        fl = 1.0 - _jaccard(_tokens(texts[0]), _tokens(texts[-1]))
        first_last.append(fl)

    return {
        "delta_avg": _mean(deltas),
        "first_last_distance": _mean(first_last),
        "runs_with_pairs": runs_with_pairs,
    }


def _redundant_consecutive_calls(sequence):
    sequence = list(sequence or [])
    if len(sequence) < 2:
        return 0
    return sum(
        1
        for index in range(len(sequence) - 1)
        if sequence[index] == sequence[index + 1]
    )


def _attempt_scores(raw):
    if not isinstance(raw, dict) or not isinstance(raw.get("attempts"), list):
        return []

    scores = []
    for attempt in raw["attempts"]:
        if not isinstance(attempt, dict):
            continue

        score = _numeric(attempt.get("score"))
        if score is None and isinstance(attempt.get("evaluation"), dict):
            score = _numeric(attempt["evaluation"].get("score"))
        if score is None:
            score = 1.0 if str(attempt.get("status", "")).lower() == "success" else 0.0
        scores.append(score)

    return scores


def _has_refinement(raw, trace):
    if isinstance(raw, dict) and len(raw.get("attempts", [])) > 1:
        return True
    return _has_key_or_event(raw, trace, "refine")


def _has_key_or_event(raw, trace, name):
    if isinstance(raw, dict) and raw.get(name) is not None:
        return True

    timeline = trace.get("timeline", []) if isinstance(trace, dict) else []
    return any(event.get("event") == name for event in timeline if isinstance(event, dict))


def _failure_recovery(raw, trace):
    if not isinstance(raw, dict) or str(raw.get("status", "")).lower() != "success":
        return False

    attempts = raw.get("attempts", [])
    if isinstance(attempts, list):
        return any(str(attempt.get("status", "")).lower() == "error" for attempt in attempts[:-1])

    if isinstance(trace, dict):
        return int(trace.get("failures", 0) or 0) > 0

    return False


def _workspace_artifacts(outputs):
    artifacts = {}
    for output in outputs:
        if not isinstance(output, dict):
            continue
        for path, metadata in (output.get("workspace_artifacts") or {}).items():
            if path == "config.json":
                continue
            artifacts[path] = metadata
    return artifacts


def _verification_metrics(outputs):
    total = 0
    passed = 0
    failed = 0
    critical_failed = 0

    for output in outputs:
        if not isinstance(output, dict):
            continue
        for result in output.get("verification_results") or []:
            if not isinstance(result, dict):
                continue
            total += 1
            if result.get("passed"):
                passed += 1
            else:
                failed += 1
                if result.get("critical", True):
                    critical_failed += 1

    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "critical_failed": critical_failed,
        "ok": critical_failed == 0,
    }


def _setup_metrics(outputs):
    total = 0
    files = 0
    dirs = 0

    for output in outputs:
        if not isinstance(output, dict):
            continue
        for result in output.get("setup_results") or []:
            if not isinstance(result, dict):
                continue
            total += 1
            if result.get("type") == "file":
                files += 1
            elif result.get("type") == "dir":
                dirs += 1

    return {"total": total, "files": files, "dirs": dirs}


def _tokens(text):
    return set(str(text or "").split())


def _jaccard(left, right):
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _numeric(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _mean(values):
    values = list(values or [])
    return round(sum(values) / len(values), 4) if values else 0.0
