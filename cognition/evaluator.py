import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class EvaluationResult:
    score: float
    passed: bool
    feedback: str
    signals: dict = field(default_factory=dict)

    def __float__(self):
        return float(self.score)

    def to_dict(self):
        return {
            "score": self.score,
            "passed": self.passed,
            "feedback": self.feedback,
            "signals": self.signals,
        }


class TaskEvaluator:
    def __init__(self, llm_judge=None, success_threshold=0.9):
        self.llm_judge = llm_judge
        self.success_threshold = float(success_threshold)

    def evaluate(self, task, plan=None, step_results=None):
        results = self._normalize_results(step_results)
        plan_score = self._plan_score(plan)
        plan_issues = self._plan_issues(plan)
        if not results:
            return EvaluationResult(
                score=0.0,
                passed=False,
                feedback="no_steps_executed",
                signals={
                    "status_score": 0.0,
                    "plan_score": plan_score,
                    "plan_issues": plan_issues,
                    "step_scores": [],
                },
            )

        status_score = self._status_score(results)
        expected_score = self._expected_score(task, results)
        llm_score = self._llm_score(task, plan, results)
        score = self._combine_scores(status_score, expected_score, llm_score)
        score = max(0.0, min(1.0, round(score, 4)))

        feedback = self._feedback(results, score, expected_score)
        passed = score >= self.success_threshold

        return EvaluationResult(
            score=score,
            passed=passed,
            feedback=feedback,
            signals={
                "status_score": status_score,
                "expected_score": expected_score,
                "llm_score": llm_score,
                "plan_score": plan_score,
                "plan_issues": plan_issues,
                "step_scores": self._step_scores(results),
                "steps": len(results),
                "failed_steps": sum(1 for result in results if not self._is_success(result)),
            },
        )

    def _normalize_results(self, step_results):
        if step_results is None:
            return []

        if isinstance(step_results, dict):
            if isinstance(step_results.get("steps"), list):
                step_results = step_results["steps"]
            else:
                step_results = [step_results]

        normalized = []
        for item in step_results:
            if isinstance(item, dict) and isinstance(item.get("result"), dict):
                normalized.append(item["result"])
            elif isinstance(item, dict):
                normalized.append(item)
            else:
                normalized.append({"status": "success", "output": item, "error": None})
        return normalized

    def _status_score(self, results):
        if not results:
            return 0.0
        successes = sum(1 for result in results if self._is_success(result))
        return successes / len(results)

    def _plan_score(self, plan):
        if not plan:
            return 0.0
        if isinstance(plan, dict):
            plan = [plan]
        if not isinstance(plan, list):
            return 0.0

        scores = []
        for step in plan:
            score = 0.0
            if isinstance(step, dict):
                if step.get("action"):
                    score += 0.6
                if isinstance(step.get("data", {}), dict):
                    score += 0.3
                if len(step) <= 4:
                    score += 0.1
            scores.append(score)
        return round(sum(scores) / len(scores), 4) if scores else 0.0

    def _plan_issues(self, plan):
        if not plan:
            return ["empty_plan"]
        if isinstance(plan, dict):
            plan = [plan]
        if not isinstance(plan, list):
            return ["plan_not_list"]

        issues = []
        for index, step in enumerate(plan):
            if not isinstance(step, dict):
                issues.append(f"step_{index}_not_dict")
                continue
            if not step.get("action"):
                issues.append(f"step_{index}_missing_action")
            if "data" in step and not isinstance(step.get("data"), dict):
                issues.append(f"step_{index}_data_not_dict")
        return issues

    def _step_scores(self, results):
        scores = []
        for index, result in enumerate(results):
            success = self._is_success(result)
            output_present = result.get("output") not in (None, "")
            score = 1.0 if success else 0.0
            if success and not output_present:
                score = 0.8
            scores.append(
                {
                    "index": index,
                    "status": str(result.get("status", "success")).lower(),
                    "score": score,
                    "has_output": output_present,
                    "error": result.get("error"),
                }
            )
        return scores

    def _is_success(self, result):
        return str(result.get("status", "success")).lower() == "success"

    def _expected_score(self, task, results):
        expected = self._expected_value(task)
        if expected is None:
            return None

        output = self._combined_output(results).lower()
        if isinstance(expected, (list, tuple, set)):
            values = [str(value).lower() for value in expected]
            if not values:
                return None
            matched = sum(1 for value in values if value in output)
            return matched / len(values)

        expected_text = str(expected).lower()
        if not expected_text:
            return None

        return 1.0 if expected_text in output else 0.0

    def _expected_value(self, task):
        if not isinstance(task, dict):
            return None

        for key in ("expected_contains", "expected_output", "expected", "contains"):
            if key in task:
                return task[key]
        return None

    def _combined_output(self, results):
        parts = []
        for result in results:
            output = result.get("output")
            error = result.get("error")
            if output is not None:
                parts.append(str(output))
            if error is not None:
                parts.append(str(error))
        return "\n".join(parts)

    def _llm_score(self, task, plan, results):
        if self.llm_judge is None:
            return None

        prompt = (
            "Avalie a execucao da tarefa de 0 a 1 e responda apenas o numero.\n\n"
            f"Tarefa: {task}\n"
            f"Plano: {plan}\n"
            f"Resultado: {self._combined_output(results)}\n"
        )

        try:
            raw = self._call_llm(prompt)
        except Exception:
            return None

        match = re.search(r"0(?:\.\d+)?|1(?:\.0+)?", str(raw))
        if not match:
            return None
        return max(0.0, min(1.0, float(match.group(0))))

    def _call_llm(self, prompt):
        generate = getattr(self.llm_judge, "generate", None)
        if callable(generate):
            try:
                return generate(prompt)
            except TypeError:
                return generate("evaluation", prompt)
        if callable(self.llm_judge):
            return self.llm_judge(prompt)
        return None

    def _combine_scores(self, status_score, expected_score, llm_score):
        if expected_score is None and llm_score is None:
            return status_score
        if expected_score is None:
            return (status_score * 0.4) + (llm_score * 0.6)
        if llm_score is None:
            return (status_score * 0.6) + (expected_score * 0.4)
        return (status_score * 0.35) + (expected_score * 0.35) + (llm_score * 0.3)

    def _feedback(self, results, score, expected_score):
        failed = [result for result in results if not self._is_success(result)]
        if failed:
            error = failed[-1].get("error") or failed[-1].get("output") or "unknown_error"
            return f"execution_failed:{error}"
        if expected_score == 0.0:
            return "expected_output_not_found"
        if score >= self.success_threshold:
            return "success"
        return "score_below_threshold"
