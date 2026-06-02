class RLTrainer:
    def __init__(self, memory):
        self.memory = memory

    def learn(self, user, response):
        try:
            score = self._evaluate(response)

            if hasattr(self.memory, "add"):
                self.memory.add(
                    text=f"{user} -> {response}",
                    memory_type="rl",
                    tags=["feedback"],
                    importance=score,
                )
        except Exception:
            pass  # não quebra o sistema

    def _evaluate(self, response):
        if not response:
            return 0.1

        if len(response) > 50:
            return 0.8

        return 0.4
