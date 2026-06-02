class LLMRouter:
    def __init__(self, llms):
        self.llms = llms or {}

    def select_model(self, goal, analysis=None):
        return self._get_model(self.select_model_key(goal, analysis))

    def generate(self, goal, prompt, analysis=None):
        selected_key = self.select_model_key(goal, analysis)
        llm = self._get_model(selected_key)

        if not llm:
            return "[LLM_ERROR] no_model_available"

        result = llm.generate(prompt)
        if not self._is_llm_error(result):
            return result

        for key in self._fallback_keys(selected_key):
            fallback = self._get_model(key)
            if not fallback:
                continue
            fallback_result = fallback.generate(prompt)
            if not self._is_llm_error(fallback_result):
                return fallback_result

        return result

    def select_model_key(self, goal, analysis=None):
        goal_lower = self._safe_lower(goal)

        if self._is_complex(analysis):
            return "power"

        if self._is_code_related(goal_lower) or self._is_action_related(goal_lower):
            return "balanced"

        return "balanced"

    def diagnostics(self):
        models = {}
        for key, client in self.llms.items():
            models[key] = getattr(client, "model", None)
        return {"models": models, "available_routes": sorted(self.llms.keys())}

    def _get_model(self, key):
        return self.llms.get(key)

    def _fallback_keys(self, selected_key):
        keys = ["balanced", "fast", "power"]
        return [key for key in keys if key != selected_key]

    def _is_llm_error(self, value):
        return isinstance(value, str) and value.startswith("[LLM_ERROR]")

    def _safe_lower(self, text):
        return str(text).lower() if text else ""

    def _is_code_related(self, goal):
        return any(k in goal for k in ["python", "código", "script"])

    def _is_action_related(self, goal):
        return any(
            k in goal
            for k in [
                "criar",
                "deletar",
                "salvar",
                "abrir",
                "executar",
                "rodar",
                "instalar",
            ]
        )

    def _is_complex(self, analysis):
        return isinstance(analysis, dict) and analysis.get("goal_type") == "complex"
