import json
import os


class RLHumanFeedback:
    def __init__(self, memory, path="rl_data.json"):
        self.memory = memory
        self.path = path
        self.data = self._load()

    def _load(self):
        if os.path.exists(self.path):
            with open(self.path, "r") as f:
                return json.load(f)
        return []

    def _save(self):
        with open(self.path, "w") as f:
            json.dump(self.data, f, indent=2)

    # 🧠 registrar interação
    def record(self, user, response):
        item = {"user": user, "response": response, "reward": None}
        self.data.append(item)
        self._save()

    # 👍👎 feedback humano
    def reward_last(self, score):
        if not self.data:
            return "Nada para avaliar."

        self.data[-1]["reward"] = score
        self._save()

        # 🧠 aprende com isso
        self.memory.add(
            text=f"{self.data[-1]['user']} -> {self.data[-1]['response']}",
            memory_type="rl",
            tags=["human_feedback"],
            importance=score,
        )

        return f"Feedback aplicado: {score}"

    # 🧠 melhorar resposta futura
    def get_best_patterns(self):
        good = [d for d in self.data if d["reward"] and d["reward"] > 0.7]

        return "\n".join(
            f"Pergunta: {d['user']}\nBoa resposta: {d['response']}" for d in good[-5:]
        )
