import random
from dataclasses import dataclass


@dataclass(frozen=True)
class ChaosConfig:
    failure_rate: float = 0.0
    seed: int | None = None
    fail_actions: tuple[str, ...] = ()
    mode: str = "timeout"
    max_failures: int | None = None


class ChaosExecutor:
    def __init__(self, executor, config=None):
        self.executor = executor
        self.config = config or ChaosConfig()
        self.random = random.Random(self.config.seed)
        self.failures = 0

    def execute(self, step, state=None):
        if self._should_fail(step):
            self.failures += 1
            action = step.get("action", "unknown") if isinstance(step, dict) else "unknown"
            return {
                "status": "error",
                "output": None,
                "error": f"chaos_{self.config.mode}:{action}",
                "chaos": True,
            }
        return self._delegate(step, state)

    def _should_fail(self, step):
        rate = max(0.0, min(1.0, float(self.config.failure_rate or 0.0)))
        if rate <= 0.0:
            return False

        if self.config.max_failures is not None and self.failures >= self.config.max_failures:
            return False

        action = step.get("action") if isinstance(step, dict) else None
        if self.config.fail_actions and action not in self.config.fail_actions:
            return False

        return self.random.random() < rate

    def _delegate(self, step, state):
        execute = getattr(self.executor, "execute", None)
        if callable(execute):
            try:
                return execute(step, state)
            except TypeError:
                return execute(step)

        if callable(self.executor):
            return self.executor(step, state)

        return {"status": "error", "output": None, "error": "executor_not_available"}
