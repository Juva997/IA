import json
import re

from benchmark.validators.common import evaluation_text, output_text


def rubric_check(test, outputs, llm_judge=None):
    detail = rubric_detail(test, outputs)
    if detail is None:
        return None
    return detail["score"]


def rubric_detail(test, outputs):
    if not _has_rubric_evaluation(test):
        return None
    if not outputs:
        return {"score": 0.0, "runs": []}

    runs = [_score_run(test, output) for output in outputs]
    return {
        "score": round(sum(run["score"] for run in runs) / len(runs), 4),
        "runs": runs,
    }


def judge_check(test, outputs, llm_judge=None):
    detail = judge_detail(test, outputs, llm_judge=llm_judge)
    if detail is None:
        return None
    return detail["score"]


def judge_detail(test, outputs, llm_judge=None):
    if llm_judge is None or not _judge_enabled(test):
        return None
    if not outputs:
        return {"score": 0.0, "runs": []}

    runs = [_judge_score(test, output, llm_judge) for output in outputs]
    valid = [run for run in runs if run["score"] is not None]
    if not valid:
        return None
    return {
        "score": round(sum(run["score"] for run in valid) / len(valid), 4),
        "runs": runs,
    }


def _has_rubric_evaluation(test):
    return bool(isinstance(test, dict) and test.get("rubric"))


def _score_run(test, output):
    return _score_rubric(test.get("rubric"), evaluation_text(output))


def _score_rubric(rubric, text):
    if not isinstance(rubric, dict):
        return {"score": 1.0, "criteria": []}

    criteria = rubric.get("criteria", rubric)
    if not isinstance(criteria, dict):
        return {"score": 1.0, "criteria": []}

    scored = []
    for name, spec in criteria.items():
        if name in {"llm_judge", "min_score"}:
            continue
        criterion = _score_criterion(name, spec, text)
        if criterion["score"] is not None:
            scored.append(criterion)

    if not scored:
        return {"score": 1.0, "criteria": []}

    total_weight = sum(item["weight"] for item in scored) or 1.0
    score = sum(item["score"] * item["weight"] for item in scored) / total_weight
    return {"score": round(score, 4), "criteria": scored}


def _score_criterion(name, spec, text):
    if isinstance(spec, (int, float)):
        return {
            "name": name,
            "score": None,
            "weight": float(spec),
            "checks": [],
        }
    if isinstance(spec, str):
        spec = {"must_contain": [spec]}
    if not isinstance(spec, dict):
        return {"name": name, "score": None, "weight": 1.0, "checks": []}

    weight = float(spec.get("weight", 1.0) or 1.0)
    checks = []
    lowered = _normalize(text)

    for concept in spec.get("must_contain", []) or []:
        checks.append(
            {
                "name": "must_contain",
                "expected": concept,
                "passed": _concept_matches(concept, lowered),
            }
        )

    for group in _any_groups(spec.get("must_contain_any")):
        checks.append(
            {
                "name": "must_contain_any",
                "expected": group,
                "passed": _concept_matches_any(group, lowered),
            }
        )

    for concept in spec.get("must_not_contain", []) or []:
        checks.append(
            {
                "name": "must_not_contain",
                "expected": concept,
                "passed": not _concept_matches(concept, lowered),
            }
        )

    for pattern in spec.get("regex", []) or []:
        checks.append(
            {
                "name": "regex",
                "expected": pattern,
                "passed": bool(re.search(str(pattern), text, flags=re.IGNORECASE | re.MULTILINE)),
            }
        )

    token_count = len(_tokens(text))
    if "min_words" in spec:
        expected = int(spec["min_words"])
        checks.append(
            {
                "name": "min_words",
                "expected": expected,
                "actual": token_count,
                "passed": token_count >= expected,
            }
        )

    if "max_words" in spec:
        expected = int(spec["max_words"])
        checks.append(
            {
                "name": "max_words",
                "expected": expected,
                "actual": token_count,
                "passed": token_count <= expected,
            }
        )

    if not checks:
        return {"name": name, "score": None, "weight": weight, "checks": []}
    score = sum(1 for check in checks if check["passed"]) / len(checks)
    return {
        "name": name,
        "score": round(score, 4),
        "weight": weight,
        "checks": checks,
    }


def _judge_enabled(test):
    return bool(
        isinstance(test, dict)
        and (
            test.get("llm_judge")
            or test.get("judge")
            or (isinstance(test.get("rubric"), dict) and test["rubric"].get("llm_judge"))
        )
    )


def _judge_score(test, output, llm_judge):
    if llm_judge is None:
        return {"score": None, "raw": None, "error": "missing_judge"}

    prompt = _judge_prompt(test, output_text(output))
    try:
        raw = _call_judge(llm_judge, prompt)
    except Exception as exc:
        return {"score": None, "raw": None, "error": str(exc)}
    return {"score": _parse_judge_score(raw), "raw": _truncate(raw)}


def _judge_prompt(test, response):
    rubric = test.get("rubric") if isinstance(test, dict) else None
    return (
        "Avalie a resposta do assistente para um benchmark.\n"
        "Responda somente JSON no formato "
        "{\"score\": 0.0, \"accuracy\": 0.0, \"completeness\": 0.0, "
        "\"instruction_following\": 0.0, \"reasoning\": 0.0, \"notes\": \"curto\"}.\n"
        "Use score entre 0 e 1.\n\n"
        f"TAREFA:\n{test.get('input', test) if isinstance(test, dict) else test}\n\n"
        f"RUBRICA:\n{json.dumps(rubric or {}, ensure_ascii=False)}\n\n"
        f"RESPOSTA:\n{response}\n"
    )


def _call_judge(llm_judge, prompt):
    generate = getattr(llm_judge, "generate", None)
    if callable(generate):
        try:
            return generate("benchmark_judge", prompt)
        except TypeError:
            return generate(prompt)
    if callable(llm_judge):
        return llm_judge(prompt)
    return None


def _parse_judge_score(raw):
    text = str(raw or "").strip()
    if not text:
        return None

    data = _extract_json_object(text)
    if isinstance(data, dict):
        dimension_scores = [
            _clamp_score(data[key])
            for key in (
                "accuracy",
                "completeness",
                "instruction_following",
                "reasoning",
            )
            if key in data
        ]
        dimension_scores = [score for score in dimension_scores if score is not None]
        if dimension_scores:
            return sum(dimension_scores) / len(dimension_scores)

        for key in ("score", "final_score", "grade"):
            if key in data:
                return _clamp_score(data[key])

    match = re.search(r"\b(?:0(?:\.\d+)?|1(?:\.0+)?|10(?:\.0+)?|[1-9](?:\.\d+)?)\b", text)
    if not match:
        return None

    value = float(match.group(0))
    if value > 1.0:
        value = value / 10.0
    return _clamp_score(value)


def _extract_json_object(text):
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except (TypeError, ValueError):
        return None


def _clamp_score(value):
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    if score > 1.0:
        score = score / 10.0
    return max(0.0, min(1.0, score))


def _concept_matches(concept, lowered_text):
    if isinstance(concept, (list, tuple, set)):
        return all(str(item).lower() in lowered_text for item in concept)
    return str(concept).lower() in lowered_text


def _concept_matches_any(concept, lowered_text):
    if isinstance(concept, (list, tuple, set)):
        return any(str(item).lower() in lowered_text for item in concept)
    return str(concept).lower() in lowered_text


def _any_groups(value):
    if value is None:
        return []
    if not isinstance(value, (list, tuple, set)):
        return [value]
    values = list(value)
    if not values:
        return []
    if all(not isinstance(item, (list, tuple, set)) for item in values):
        return [values]
    return values


def _normalize(text):
    return " ".join(str(text or "").lower().split())


def _tokens(text):
    return re.findall(r"\w+", str(text or ""), flags=re.UNICODE)


def _truncate(value, limit=2000):
    text = str(value or "")
    if len(text) <= limit:
        return text
    return text[:limit] + "...[truncated]"
