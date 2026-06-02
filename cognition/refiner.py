class Refiner:
    def __init__(self, max_attempts_kept=10):
        self.max_attempts_kept = max(1, int(max_attempts_kept or 10))

    def refine(self, state, execution, evaluation):
        next_state = dict(state or {})
        attempts = list(next_state.get("attempts", []))
        attempt = self._attempt_record(execution, evaluation)
        attempts.append(attempt)

        next_state["attempts"] = attempts[-self.max_attempts_kept :]
        next_state["last_error"] = self._last_error(execution, evaluation)
        next_state["last_score"] = getattr(evaluation, "score", 0.0)
        next_state["strategy"] = self._strategy(execution, evaluation)
        next_state["retry_count"] = int(next_state.get("retry_count", 0)) + 1
        return next_state

    def build_context(self, context, state):
        merged = dict(context or {})
        state = state or {}
        merged["closed_loop"] = {
            "last_error": state.get("last_error"),
            "last_score": state.get("last_score"),
            "strategy": state.get("strategy"),
            "retry_count": state.get("retry_count", 0),
            "attempts": state.get("attempts", [])[-3:],
        }
        return merged

    def _attempt_record(self, execution, evaluation):
        return {
            "plan": (execution or {}).get("plan", []),
            "score": getattr(evaluation, "score", 0.0),
            "feedback": getattr(evaluation, "feedback", "unknown"),
            "errors": self._errors(execution),
        }

    def _errors(self, execution):
        errors = []
        for item in (execution or {}).get("steps", []):
            result = item.get("result", {}) if isinstance(item, dict) else {}
            if str(result.get("status", "")).lower() == "error":
                errors.append(result.get("error") or result.get("output") or "unknown_error")
        return errors

    def _last_error(self, execution, evaluation):
        errors = self._errors(execution)
        if errors:
            return errors[-1]
        feedback = getattr(evaluation, "feedback", None)
        if feedback and feedback != "success":
            return feedback
        return None

    def _strategy(self, execution, evaluation):
        errors = " ".join(self._errors(execution)).lower()
        feedback = str(getattr(evaluation, "feedback", "")).lower()

        if "tool_not_found" in errors:
            return "choose_available_tool"
        if "syntax" in errors or "indent" in errors:
            return "repair_code_before_execution"
        if "timeout" in errors:
            return "simplify_or_limit_runtime"
        if "expected_output" in feedback:
            return "add_output_validation_step"
        return "revise_plan_with_last_error"
