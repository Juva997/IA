from cognition.evaluator import EvaluationResult
from core.chaos import ChaosConfig, ChaosExecutor
from core.task_agents import V5Agent, V6Agent, V7Agent
from memory.experience_store import ExperienceStore


class StaticPlanner:
    def __init__(self, plan):
        self.plan = plan

    def create_plan(self, goal, context, analysis=None):
        return self.plan


class RecoveringPlanner:
    def __init__(self):
        self.contexts = []

    def create_plan(self, goal, context, analysis=None):
        self.contexts.append(context)
        closed_loop = context.get("closed_loop", {})
        if closed_loop.get("last_error"):
            return [{"action": "ok", "data": {}}]
        return [{"action": "bad", "data": {}}]


class CapturingPlanner:
    def __init__(self):
        self.contexts = []

    def create_plan(self, goal, context, analysis=None):
        self.contexts.append(context)
        return [{"action": "ok", "data": {}}]


class FakeExecutor:
    def execute(self, step, state):
        if step["action"] == "bad":
            return {"status": "error", "output": None, "error": "boom"}
        return {"status": "success", "output": "ok done", "error": None}


def test_v5_agent_executes_plan_and_scores_expected_output():
    agent = V5Agent(
        StaticPlanner([{"action": "ok", "data": {}}]),
        FakeExecutor(),
    )

    result = agent.run({"input": "run task", "expected": "done"})

    assert result["version"] == "v5"
    assert result["status"] == "success"
    assert result["score"] == 1.0
    assert result["output"] == "ok done"
    assert result["evaluation"]["signals"]["plan_score"] == 1.0
    assert result["evaluation"]["signals"]["step_scores"][0]["score"] == 1.0
    assert result["trace"]["steps"] == 1
    assert result["cost"]["estimated_tool_calls"] == 1


def test_v6_agent_refines_after_failed_attempt():
    planner = RecoveringPlanner()
    agent = V6Agent(planner, FakeExecutor(), max_iterations=2)

    result = agent.run("recover task")

    assert result["version"] == "v6"
    assert result["status"] == "success"
    assert result["iterations"] == 2
    assert len(result["attempts"]) == 2
    assert planner.contexts[1]["closed_loop"]["last_error"] == "boom"
    assert result["simulation"]["status"] == "success"
    assert result["critique"]["approved"] is True
    assert result["verification"]["passed"] is True


def test_v6_agent_reports_critique_for_empty_plan():
    agent = V6Agent(StaticPlanner([]), FakeExecutor(), max_iterations=1)

    result = agent.run("empty task")

    assert result["status"] == "error"
    assert result["simulation"]["issues"] == ["empty_plan"]
    assert result["critique"]["approved"] is False
    assert result["trace"]["failures"] == 0


def test_chaos_executor_injects_deterministic_failures():
    executor = ChaosExecutor(
        FakeExecutor(),
        ChaosConfig(failure_rate=1.0, seed=1, max_failures=1),
    )
    agent = V6Agent(StaticPlanner([{"action": "ok", "data": {}}]), executor)

    result = agent.run("chaos task")

    assert result["status"] == "success"
    assert result["iterations"] == 2
    assert result["attempts"][0]["error"].startswith("execution_failed:chaos_timeout")


def test_v7_agent_records_experience_and_reuses_similar_tasks(tmp_path):
    store = ExperienceStore(path=str(tmp_path / "experiences.json"))
    store.record(
        "similar task",
        [{"action": "ok", "data": {}}],
        {"steps": [], "output": "ok"},
        EvaluationResult(score=1.0, passed=True, feedback="success"),
    )
    planner = CapturingPlanner()
    agent = V7Agent(
        planner,
        FakeExecutor(),
        experience_store=store,
        max_iterations=1,
    )

    result = agent.run({"input": "similar task", "expected": "ok"})

    assert result["version"] == "v7"
    assert result["status"] == "success"
    assert planner.contexts[0]["experience"]
    assert planner.contexts[0]["success_patterns"]
    assert result["learning_metrics"]["knowledge_reuse"] > 0
    assert result["policy"]["mode"] in {
        "explore",
        "refine_strategy",
        "reuse_successful_patterns",
    }


def test_experience_store_discards_low_score_reuse(tmp_path):
    store = ExperienceStore(path=str(tmp_path / "experiences.json"), min_reuse_score=0.7)
    store.record(
        "same task",
        [{"action": "bad", "data": {}}],
        {"steps": [], "output": "bad"},
        EvaluationResult(score=0.2, passed=False, feedback="fail"),
    )
    store.record(
        "same task",
        [{"action": "ok", "data": {}}],
        {"steps": [], "output": "ok"},
        EvaluationResult(score=0.95, passed=True, feedback="success"),
    )

    similar = store.retrieve_similar("same task")

    assert len(similar) == 1
    assert similar[0]["score"] == 0.95
    assert similar[0]["reuse_rank"] > 0
