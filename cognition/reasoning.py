class Reasoning:
    def analyze(self, goal, context):
        goal_type = self._detect_type(goal)
        hints = self._generate_hints(goal)

        # 🔥 usa memória
        facts = context.get("facts", {})

        return {"goal_type": goal_type, "hints": hints, "known_facts": facts}

    def _detect_type(self, goal):
        g = goal.lower()

        if "nome" in g:
            return "memory"
        if "python" in g or "código" in g:
            return "code"
        if "arquivo" in g:
            return "filesystem"

        return "general"

    def _generate_hints(self, goal):
        g = goal.lower()
        hints = []

        if "criar" in g:
            hints.append("escrever algo")

        if "ler" in g:
            hints.append("ler dados")

        return hints
