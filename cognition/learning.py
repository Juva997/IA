class PolicyUpdater:
    def update(self, experiences):
        experiences = list(experiences or [])
        if not experiences:
            return {"mode": "explore", "confidence": 0.0}

        recent = experiences[-20:]
        success_rate = sum(1 for item in recent if self._passed(item)) / len(recent)
        avg_score = sum(float(item.get("score", 0.0)) for item in recent) / len(recent)

        if success_rate >= 0.8 and avg_score >= 0.85:
            mode = "reuse_successful_patterns"
        elif success_rate >= 0.5:
            mode = "refine_strategy"
        else:
            mode = "explore"

        return {
            "mode": mode,
            "confidence": round((success_rate + avg_score) / 2, 4),
            "success_rate": round(success_rate, 4),
            "avg_score": round(avg_score, 4),
        }

    def _passed(self, item):
        if "passed" in item:
            return bool(item.get("passed"))
        return item.get("feedback") == "success"


class LearningModule:
    def __init__(self, policy_updater=None):
        self.experiences = []
        self.policy_updater = policy_updater or PolicyUpdater()
        self.policy = {"mode": "explore", "confidence": 0.0}

    def record(self, step, result, feedback):
        self.experiences.append({"step": step, "result": result, "feedback": feedback})

    def record_experience(self, experience):
        self.experiences.append(dict(experience or {}))
        self.policy = self.policy_updater.update(self.experiences)
        return self.policy

    def update_policy(self, history=None):
        if history is not None:
            self.experiences = list(history)
        self.policy = self.policy_updater.update(self.experiences)
        return self.policy

    def improve_strategy(self):
        success = [e for e in self.experiences if self._is_success(e)]

        if len(success) > 5:
            return "refine_strategy"

        return "explore"

    def _is_success(self, experience):
        if "passed" in experience:
            return bool(experience.get("passed"))
        return experience.get("feedback") == "success"
