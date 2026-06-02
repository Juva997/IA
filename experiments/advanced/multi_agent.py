class MultiAgentSystem:
    def __init__(self, llm):
        self.llm = llm

    def run(self, goal):
        responses = [
            self._agent("DEV", goal),
            self._agent("HACKER", goal),
            self._agent("ANALYST", goal),
        ]

        return self._critic(goal, responses)

    def _agent(self, role, goal):
        return self.llm.generate(f"[{role}] Resolva:\n{goal}")

    def _critic(self, goal, responses):
        return self.llm.generate(f"""
Escolha a melhor resposta para:

{goal}

Respostas:
{responses}

Resposta final:
""")


class MultiAgentDebate:
    def __init__(self, llm):
        self.llm = llm

    def run(self, task):
        planner = self.llm.generate(f"Plano:\n{task}")
        dev = self.llm.generate(f"Execute:\n{planner}")
        critic = self.llm.generate(f"Critique:\n{dev}")

        return self.llm.generate(f"""
Melhore:

Plano: {planner}
Execução: {dev}
Crítica: {critic}

Final:
""")
