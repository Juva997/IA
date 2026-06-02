from benchmark.process_metrics import compute_process_metrics


def compute_efficiency_factor(expectations, process):
    expectations = expectations or {}
    budget = expectations.get("efficiency_budget")
    if not isinstance(budget, dict):
        return 1.0

    mapping = (
        ("steps", "steps"),
        ("tool_calls", "tool_calls"),
        ("agent_steps", "agent_steps"),
        ("benchmark_steps", "benchmark_steps"),
    )
    factor = 1.0
    for budget_key, process_key in mapping:
        if budget_key not in budget:
            continue
        limit = float(budget[budget_key])
        if limit <= 0:
            continue
        actual = float(process.get(process_key, 0) or 0)
        if actual <= limit:
            continue
        factor *= limit / actual

    return round(max(0.0, min(1.0, factor)), 4)


def process_check(test, outputs):
    expectations = test.get("expectations", {}) if isinstance(test, dict) else {}
    if not expectations:
        return 1.0

    process = compute_process_metrics(outputs)
    checks = _check_results(expectations, process)
    if not checks:
        return 1.0

    if any(check["critical"] and not check["passed"] for check in checks):
        return 0.0

    total_weight = sum(check["weight"] for check in checks) or 1.0
    score = sum(check["weight"] for check in checks if check["passed"]) / total_weight
    return round(score, 4)


def validate_process(process, expectations):
    return all(check["passed"] for check in _check_results(expectations or {}, process or {}))


def _checks(expectations, process):
    return [check["passed"] for check in _check_results(expectations, process)]


def _check_results(expectations, process):
    checks = []
    weights = expectations.get("process_weights", {})
    critical = set(expectations.get("critical_expectations", []))

    if "min_steps" in expectations:
        checks.append(
            _check(
                "min_steps",
                int(process.get("steps", 0)) >= int(expectations["min_steps"]),
                weights,
                critical,
            )
        )

    if "min_agent_steps" in expectations:
        checks.append(
            _check(
                "min_agent_steps",
                int(process.get("agent_steps", 0))
                >= int(expectations["min_agent_steps"]),
                weights,
                critical,
            )
        )

    if "min_benchmark_steps" in expectations:
        checks.append(
            _check(
                "min_benchmark_steps",
                int(process.get("benchmark_steps", 0))
                >= int(expectations["min_benchmark_steps"]),
                weights,
                critical,
            )
        )

    if expectations.get("requires_tools"):
        checks.append(
            _check(
                "requires_tools",
                int(process.get("tool_calls", 0)) > 0
                or int(process.get("workspace_writes", 0)) > 0,
                weights,
                critical,
            )
        )

    if expectations.get("requires_trace"):
        checks.append(
            _check("requires_trace", bool(process.get("has_trace")), weights, critical)
        )

    if expectations.get("requires_refinement"):
        checks.append(
            _check(
                "requires_refinement",
                bool(process.get("has_refinement")),
                weights,
                critical,
            )
        )

    if expectations.get("requires_critic"):
        checks.append(
            _check("requires_critic", bool(process.get("has_critic")), weights, critical)
        )

    if expectations.get("requires_verification"):
        checks.append(
            _check(
                "requires_verification",
                bool(process.get("has_verification")),
                weights,
                critical,
            )
        )

    if expectations.get("requires_benchmark_verification"):
        checks.append(
            _check(
                "requires_benchmark_verification",
                int(process.get("verification_total", 0) or 0) > 0,
                weights,
                critical,
            )
        )

    if expectations.get("verification_must_pass"):
        checks.append(
            _check(
                "verification_must_pass",
                int(process.get("verification_critical_failed", 0) or 0) == 0,
                weights,
                critical,
            )
        )

    if "min_iterations" in expectations:
        checks.append(
            _check(
                "min_iterations",
                float(process.get("iterations_avg", 0.0))
                >= float(expectations["min_iterations"]),
                weights,
                critical,
            )
        )

    if "min_improvement_gain" in expectations:
        checks.append(
            _check(
                "min_improvement_gain",
                float(process.get("improvement_gain", 0.0))
                >= float(expectations["min_improvement_gain"]),
                weights,
                critical,
            )
        )

    if "min_iteration_semantic_delta" in expectations:
        threshold = float(expectations["min_iteration_semantic_delta"])
        runs_with_pairs = int(process.get("iteration_semantic_runs_with_pairs", 0) or 0)
        delta_avg = float(process.get("iteration_semantic_delta_avg", 0.0))
        checks.append(
            _check(
                "min_iteration_semantic_delta",
                runs_with_pairs == 0 or delta_avg >= threshold,
                weights,
                critical,
            )
        )

    if "min_stability_score" in expectations:
        checks.append(
            _check(
                "min_stability_score",
                float(process.get("stability_score", 0.0))
                >= float(expectations["min_stability_score"]),
                weights,
                critical,
            )
        )

    if "min_semantic_stability_score" in expectations:
        checks.append(
            _check(
                "min_semantic_stability_score",
                float(process.get("semantic_stability_score", 0.0))
                >= float(expectations["min_semantic_stability_score"]),
                weights,
                critical,
            )
        )

    if "required_tools" in expectations:
        required = set(expectations.get("required_tools") or [])
        checks.append(
            _check(
                "required_tools",
                required.issubset(set(process.get("tools", []))),
                weights,
                critical,
            )
        )

    if "required_tool_order" in expectations:
        checks.append(
            _check(
                "required_tool_order",
                _contains_ordered(
                    process.get("tool_sequence", []),
                    expectations.get("required_tool_order") or [],
                ),
                weights,
                critical,
            )
        )

    if "exact_tool_sequence" in expectations:
        checks.append(
            _check(
                "exact_tool_sequence",
                list(process.get("tool_sequence", []))
                == list(expectations.get("exact_tool_sequence") or []),
                weights,
                critical,
            )
        )

    if "tool_dependencies" in expectations:
        checks.append(
            _check(
                "tool_dependencies",
                _tool_dependencies_satisfied(
                    process.get("tool_sequence", []),
                    expectations.get("tool_dependencies") or [],
                ),
                weights,
                critical,
            )
        )

    if "max_steps" in expectations:
        checks.append(
            _check(
                "max_steps",
                int(process.get("steps", 0)) <= int(expectations["max_steps"]),
                weights,
                critical,
            )
        )

    if "max_agent_steps" in expectations:
        checks.append(
            _check(
                "max_agent_steps",
                int(process.get("agent_steps", 0))
                <= int(expectations["max_agent_steps"]),
                weights,
                critical,
            )
        )

    if "max_benchmark_steps" in expectations:
        checks.append(
            _check(
                "max_benchmark_steps",
                int(process.get("benchmark_steps", 0))
                <= int(expectations["max_benchmark_steps"]),
                weights,
                critical,
            )
        )

    if "max_tool_calls" in expectations:
        checks.append(
            _check(
                "max_tool_calls",
                int(process.get("tool_calls", 0))
                <= int(expectations["max_tool_calls"]),
                weights,
                critical,
            )
        )

    if "max_redundant_tool_calls" in expectations:
        checks.append(
            _check(
                "max_redundant_tool_calls",
                int(process.get("redundant_tool_calls", 0))
                <= int(expectations["max_redundant_tool_calls"]),
                weights,
                critical,
            )
        )

    if "expected_files" in expectations:
        expected = set(expectations.get("expected_files") or [])
        checks.append(
            _check(
                "expected_files",
                expected.issubset(set(process.get("workspace_files", []))),
                weights,
                critical,
            )
        )

    if "expected_file_contents" in expectations:
        checks.append(
            _check(
                "expected_file_contents",
                _file_contents_match(
                    process.get("workspace_artifacts", {}),
                    expectations.get("expected_file_contents") or {},
                ),
                weights,
                critical,
            )
        )

    return checks


def _check(name, passed, weights, critical):
    return {
        "name": name,
        "passed": bool(passed),
        "weight": float(weights.get(name, 1.0)),
        "critical": name in critical,
    }


def _tool_dependencies_satisfied(sequence, dependencies):
    if not dependencies:
        return True

    for pair in dependencies:
        if (
            not isinstance(pair, (list, tuple))
            or len(pair) != 2
            or pair[0] is None
            or pair[1] is None
        ):
            continue
        before, after = pair[0], pair[1]
        if not _ordered_tool_pair(sequence, before, after):
            return False
    return True


def _ordered_tool_pair(sequence, before, after):
    indices_before = [index for index, tool in enumerate(sequence) if tool == before]
    indices_after = [index for index, tool in enumerate(sequence) if tool == after]
    if not indices_before or not indices_after:
        return False
    return any(i < j for i in indices_before for j in indices_after)


def _contains_ordered(sequence, required):
    if not required:
        return True

    position = 0
    for item in sequence:
        if item == required[position]:
            position += 1
            if position == len(required):
                return True
    return False


def _file_contents_match(artifacts, expected):
    if not expected:
        return True

    for path, rule in expected.items():
        artifact = artifacts.get(path)
        if not artifact:
            return False

        text = artifact.get("text")
        if isinstance(rule, str):
            if text is None or rule not in text:
                return False
            continue

        if not isinstance(rule, dict):
            return False

        if "contains" in rule and (text is None or rule["contains"] not in text):
            return False
        if "equals" in rule and text != rule["equals"]:
            return False
        if "sha256" in rule and artifact.get("sha256") != rule["sha256"]:
            return False

    return True
