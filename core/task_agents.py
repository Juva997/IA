from cognition.evaluator import EvaluationResult, TaskEvaluator
from cognition.learning import LearningModule
from cognition.refiner import Refiner
from core.execution_trace import ExecutionTracer
from memory.experience_store import ExperienceStore


class V5Agent:
    version = "v5"

    def __init__(
        self,
        planner,
        executor,
        evaluator=None,
        memory=None,
        tracer_factory=None,
    ):
        self.planner = planner
        self.executor = executor
        self.evaluator = evaluator or TaskEvaluator()
        self.memory = memory
        self.tracer_factory = tracer_factory or ExecutionTracer

    def run(self, task):
        state = self._initial_state(task)
        state["iteration"] = 1
        context = self._build_context(task, state)
        plan = self.plan(task, context, state)
        execution = self.execute(plan, state)
        evaluation = self.evaluate(task, plan, execution)
        self._store_steps(execution, evaluation)
        result = self._result(task, plan, execution, evaluation, iterations=1)
        return self._finalize_result(result)

    def plan(self, task, context=None, state=None):
        task_text = self._task_text(task)
        planner = self.planner

        if planner is None:
            return []

        create_plan = getattr(planner, "create_plan", None)
        if callable(create_plan):
            try:
                return self._normalize_plan(create_plan(task_text, context or {}, None))
            except TypeError:
                try:
                    return self._normalize_plan(create_plan(task_text, context or {}))
                except TypeError:
                    return self._normalize_plan(create_plan(task_text))

        plan = getattr(planner, "plan", None)
        if callable(plan):
            try:
                return self._normalize_plan(plan(task_text, context or {}, state or {}))
            except TypeError:
                try:
                    return self._normalize_plan(plan(task_text, context or {}))
                except TypeError:
                    return self._normalize_plan(plan(task_text))

        if callable(planner):
            return self._normalize_plan(planner(task_text))

        return []

    def execute(self, plan, state=None):
        records = []
        state = state or {}
        trace = state.get("trace")
        if trace:
            trace.add_event("execute_start", {"steps": len(plan or [])})

        for step in plan or []:
            span = trace.start_step(step, state.get("iteration")) if trace else None
            result = self._execute_step(step, state)
            trace_event = trace.end_step(span, result) if trace and span else None
            record = {"step": step, "result": result}
            if trace_event:
                record["trace"] = {
                    "step_id": trace_event["step_id"],
                    "duration": trace_event["duration"],
                }
            records.append(record)
            state.setdefault("history", []).append(record)

        if trace:
            trace.add_event("execute_end", {"steps": len(records)})

        return {
            "steps": records,
            "output": self._last_output(records),
            "cost": self._execution_cost(records),
            "trace": trace.to_dict() if trace else None,
        }

    def evaluate(self, task, plan, execution):
        return self.evaluator.evaluate(task, plan=plan, step_results=execution.get("steps", []))

    def _execute_step(self, step, state):
        execute = getattr(self.executor, "execute", None)
        if callable(execute):
            try:
                return execute(step, state)
            except TypeError:
                return execute(step)

        if callable(self.executor):
            return self.executor(step, state)

        return {"status": "error", "output": None, "error": "executor_not_available"}

    def _build_context(self, task, state):
        task_text = self._task_text(task)
        if self.memory is not None:
            build_context = getattr(self.memory, "build_context", None)
            if callable(build_context):
                try:
                    context = build_context(task_text, state)
                except TypeError:
                    context = build_context(task_text)
                if isinstance(context, dict):
                    context.setdefault("goal", task_text)
                    context.setdefault("recent_history", state.get("history", []))
                    return context

        return {
            "goal": task_text,
            "recent_history": state.get("history", []),
            "retrieved_memory": [],
            "facts": {},
        }

    def _store_steps(self, execution, evaluation):
        if self.memory is None:
            return

        store_step = getattr(self.memory, "store_step", None)
        if not callable(store_step):
            return

        for record in execution.get("steps", []):
            try:
                store_step(record.get("step"), record.get("result"), evaluation.feedback)
            except Exception:
                pass

    def _initial_state(self, task):
        return {
            "task": self._task_text(task),
            "history": [],
            "attempts": [],
            "metadata": {},
            "trace": self.tracer_factory(),
        }

    def _normalize_plan(self, plan):
        if plan is None:
            return []
        if isinstance(plan, dict):
            return [plan]
        if isinstance(plan, list):
            return [step for step in plan if isinstance(step, dict)]
        return []

    def _result(self, task, plan, execution, evaluation, iterations, attempts=None):
        status = "success" if evaluation.passed else "error"
        output = execution.get("output")
        result = {
            "version": self.version,
            "status": status,
            "task": self._task_text(task),
            "plan": plan,
            "steps": execution.get("steps", []),
            "output": output,
            "score": evaluation.score,
            "evaluation": evaluation.to_dict(),
            "iterations": iterations,
            "trace": self._trace_dict(execution),
            "cost": execution.get("cost", self._execution_cost(execution.get("steps", []))),
        }
        if attempts is not None:
            result["attempts"] = attempts
        if status == "error":
            result["error"] = evaluation.feedback
        return result

    def _attempt_result(self, task, plan, execution, evaluation, iteration):
        return self._result(task, plan, execution, evaluation, iterations=iteration)

    def _last_output(self, records):
        for record in reversed(records):
            result = record.get("result", {})
            if result.get("output") not in (None, ""):
                return result.get("output")
            if result.get("error"):
                return result.get("error")
        return ""

    def _execution_cost(self, records):
        failures = 0
        for record in records or []:
            result = record.get("result", {}) if isinstance(record, dict) else {}
            if str(result.get("status", "")).lower() == "error":
                failures += 1
        return {
            "steps": len(records or []),
            "failed_steps": failures,
            "estimated_tool_calls": len(records or []),
        }

    def _trace_dict(self, execution):
        trace = execution.get("trace") if isinstance(execution, dict) else None
        if trace:
            return trace
        return None

    def _task_text(self, task):
        if isinstance(task, dict):
            return str(task.get("input") or task.get("task") or task.get("goal") or task)
        return str(task)

    def _finalize_result(self, result):
        return result


class V6Agent(V5Agent):
    version = "v6"

    def __init__(
        self,
        planner,
        executor,
        evaluator=None,
        memory=None,
        refiner=None,
        max_iterations=10,
    ):
        super().__init__(planner, executor, evaluator=evaluator, memory=memory)
        self.refiner = refiner or Refiner()
        self.max_iterations = max(1, int(max_iterations or 10))

    def run(self, task):
        state = self._initial_state(task)
        attempts = []
        last_result = None

        for iteration in range(1, self.max_iterations + 1):
            state["iteration"] = iteration
            context = self._prepare_context(task, state)
            plan = self.plan(task, context, state)
            simulation = self.simulate(plan, state)
            critique = self.critique(task, plan, simulation, state)

            if critique["approved"]:
                execution = self.execute(plan, state)
                evaluation = self.evaluate(task, plan, execution)
                verification = self.verify(task, plan, execution, evaluation, state)
                evaluation = self._apply_verification(evaluation, verification)
            else:
                execution = self._skipped_execution(state)
                evaluation = self._critique_evaluation(simulation, critique)
                verification = self.verify(task, plan, execution, evaluation, state)

            self._store_steps(execution, evaluation)
            self._after_attempt(task, plan, execution, evaluation, state, iteration)

            attempt = self._attempt_result(task, plan, execution, evaluation, iteration)
            attempt["simulation"] = simulation
            attempt["critique"] = critique
            attempt["verification"] = verification
            attempts.append(attempt)
            last_result = self._result(
                task,
                plan,
                execution,
                evaluation,
                iterations=iteration,
                attempts=attempts,
            )
            last_result["simulation"] = simulation
            last_result["critique"] = critique
            last_result["verification"] = verification

            if evaluation.passed:
                return self._finalize_result(last_result)

            state = self.refiner.refine(
                state,
                {"plan": plan, "steps": execution.get("steps", [])},
                evaluation,
            )

        if last_result is None:
            evaluation = self.evaluator.evaluate(task, plan=[], step_results=[])
            last_result = self._result(
                task,
                [],
                {"steps": [], "output": ""},
                evaluation,
                iterations=0,
                attempts=attempts,
            )

        last_result["status"] = "error"
        last_result.setdefault("error", "max_iterations_reached")
        return self._finalize_result(last_result)

    def _prepare_context(self, task, state):
        context = self._build_context(task, state)
        return self.refiner.build_context(context, state)

    def _after_attempt(self, task, plan, execution, evaluation, state, iteration):
        return None

    def simulate(self, plan, state=None):
        state = state or {}
        trace = state.get("trace")
        issues = self._plan_issues(plan)
        result = {
            "status": "success" if not issues else "error",
            "steps": len(plan or []),
            "issues": issues,
        }
        if trace:
            trace.add_event("simulate", result)
        return result

    def critique(self, task, plan, simulation, state=None):
        issues = list(simulation.get("issues", []))
        approved = simulation.get("status") == "success"
        if len(plan or []) > 50:
            approved = False
            issues.append("plan_too_large")

        result = {
            "approved": approved,
            "feedback": "plan_approved" if approved else ";".join(issues),
            "issues": issues,
        }
        trace = (state or {}).get("trace")
        if trace:
            trace.add_event("critique", result)
        return result

    def verify(self, task, plan, execution, evaluation, state=None):
        failed_steps = evaluation.signals.get("failed_steps", 0)
        passed = bool(evaluation.passed and failed_steps == 0)
        feedback = "verified" if passed else evaluation.feedback
        result = {
            "passed": passed,
            "feedback": feedback,
            "score": evaluation.score,
            "failed_steps": failed_steps,
        }
        trace = (state or {}).get("trace")
        if trace:
            trace.add_event("verify", result)
        return result

    def _apply_verification(self, evaluation, verification):
        if verification.get("passed"):
            return evaluation

        signals = dict(evaluation.signals)
        signals["verification"] = verification
        return EvaluationResult(
            score=min(float(evaluation.score), 0.89),
            passed=False,
            feedback=verification.get("feedback", "verification_failed"),
            signals=signals,
        )

    def _critique_evaluation(self, simulation, critique):
        return EvaluationResult(
            score=0.0,
            passed=False,
            feedback=f"critique_failed:{critique.get('feedback', 'unknown')}",
            signals={
                "simulation": simulation,
                "critique": critique,
                "status_score": 0.0,
                "failed_steps": 0,
            },
        )

    def _skipped_execution(self, state):
        trace = (state or {}).get("trace")
        if trace:
            trace.add_event("execute_skipped", {"reason": "critique_failed"})
        return {
            "steps": [],
            "output": "",
            "cost": {"steps": 0, "failed_steps": 0, "estimated_tool_calls": 0},
            "trace": trace.to_dict() if trace else None,
        }

    def _plan_issues(self, plan):
        if not plan:
            return ["empty_plan"]
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


class V7Agent(V6Agent):
    version = "v7"

    def __init__(
        self,
        planner,
        executor,
        evaluator=None,
        memory=None,
        refiner=None,
        experience_store=None,
        learning_module=None,
        max_iterations=10,
    ):
        super().__init__(
            planner,
            executor,
            evaluator=evaluator,
            memory=memory,
            refiner=refiner,
            max_iterations=max_iterations,
        )
        self.experience_store = experience_store or ExperienceStore(memory=memory)
        self.learning_module = learning_module or LearningModule()

    def _prepare_context(self, task, state):
        context = super()._prepare_context(task, state)
        experiences = self.experience_store.retrieve_similar(task)
        state["used_experiences"] = len(experiences)
        context["experience"] = experiences
        context["success_patterns"] = self.experience_store.summarize_success_patterns()
        context["policy"] = getattr(self.learning_module, "policy", {})
        return context

    def _after_attempt(self, task, plan, execution, evaluation, state, iteration):
        experience = self.experience_store.record(
            task,
            plan,
            execution,
            evaluation,
            metadata={
                "attempts": iteration,
                "used_experiences": state.get("used_experiences", 0),
            },
        )
        record_experience = getattr(self.learning_module, "record_experience", None)
        if callable(record_experience):
            state["policy"] = record_experience(experience)

    def _finalize_result(self, result):
        result = dict(result)
        result["learning_metrics"] = self.experience_store.learning_metrics()
        result["policy"] = getattr(self.learning_module, "policy", {})
        return result
