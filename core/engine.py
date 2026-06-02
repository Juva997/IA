import traceback
import os

from monitor.logger import Logger


class AutonomousEngine:
    def __init__(
        self,
        agent,
        planner,
        memory,
        executor,
        critic,
        router=None,
        event_bus=None,
        guard=None,
        max_iterations=10,
        max_failures=3,
        debug=True,
    ):
        self.agent = agent
        self.planner = planner
        self.memory = memory
        self.executor = executor
        self.critic = critic
        self.router = router
        self.event_bus = event_bus
        self.guard = guard

        self.max_iterations = max_iterations
        self.max_failures = max_failures
        self.debug = debug
        self.logger = Logger()
        self.feedback_trainer = None  # Lazy load
        self.workspace_root = os.getcwd()
        self.sandbox_root = None
        # session_context centralizado quando possível (compatibilidade)
        try:
            from core.state import state_manager

            self.session_context = state_manager.session_state.metadata.setdefault(
                "session_context", {"last_folder_path": None, "last_file_path": None}
            )
        except Exception:
            self.session_context = {"last_folder_path": None, "last_file_path": None}

    # =========================
    # 🚀 LOOP PRINCIPAL (ESTÁVEL)
    # =========================
    def run(self, goal):
        state = self._init_state(goal)
        failures = 0

        self._log(f"[ENGINE] Start goal: {goal}")

        try:
            # 🔥 contexto inicial
            context = self._build_context(goal, state)

            # 🔥 memória direta (super importante)
            memory_answer = self._handle_memory_question(goal, context)
            if memory_answer:
                return self._success(memory_answer)

            # 🔥 conversa simples (evita planner)
            if self._is_simple_chat(goal):
                return self._success(self.agent.respond(goal, context))

            # 🔁 LOOP CONTROLADO
            while self._should_continue(state):
                state.iteration += 1

                context = self._build_context(goal, state)

                route = self._route_if_available(goal, context, state)
                context["route"] = route

                analysis = self._analyze_if_available(goal, context)

                plan, goal_type = self._create_plan(goal, context, analysis)

                # 🔥 fallback crítico
                if self._is_invalid_plan(plan):
                    self._log("[ENGINE] Fallback -> direct response")
                    return self._handle_direct_response(goal, context, goal_type)

                if self._is_direct_response(plan, goal_type):
                    return self._handle_direct_response(goal, context, goal_type)

                self._emit("plan_created", plan)

                result, failures = self._execute_plan(plan, state, goal, failures)

                if result:
                    return result

                # 🔥 proteção contra loop infinito
                if state.iteration >= self.max_iterations - 1:
                    self._log("[ENGINE] Max iterations fallback")
                    return self._success(self.agent.respond(goal, context))

        except Exception as e:
            self._handle_error(e)

        return self._max_iterations_error()

    # =========================
    # 🧠 MEMÓRIA
    # =========================
    def _handle_memory_question(self, goal, context):
        goal = str(goal).lower()
        facts = context.get("facts", {})

        if self._is_memory_statement(goal):
            return self._memory_statement_response(context)

        if "meu nome" in goal:
            name = facts.get("user_name")
            if name:
                return f"Seu nome é {name}."
            return "Ainda não sei seu nome."

        return None

    def _is_memory_statement(self, goal):
        memory_markers = [
            "lembre-se",
            "lembre que",
            "memorize",
            "guarde",
            "meu nome é",
            "meu nome é",
            "me chamo",
            "gosto de",
        ]
        return any(marker in goal for marker in memory_markers)

    def _memory_statement_response(self, context):
        facts = context.get("facts", {})

        if facts.get("user_name"):
            return f"Memória atualizada: seu nome é {facts['user_name']}."

        details = []
        if facts.get("likes"):
            details.append(f"gostos: {', '.join(facts['likes'])}")
        if facts.get("programming_language"):
            details.append(f"linguagem: {facts['programming_language']}")

        if details:
            return "Memória atualizada (" + "; ".join(details) + ")."
        return "Memória atualizada."

    # =========================
    # 💬 CHAT DETECTION
    # =========================
    def _is_simple_chat(self, goal):
        if not isinstance(goal, str):
            return False

        goal = goal.strip().lower()

        # 🔥 cumprimentos
        greetings = ["oi", "olá", "ola", "hello", "hi"]
        if goal in greetings:
            return True

        # 🔥 evitar classificar comandos curtos de ação como chat
        action_keywords = [
            "criar",
            "crie",
            "cria",
            "deletar",
            "delete",
            "apagar",
            "salvar",
            "salve",
            "abrir",
            "executar",
            "rodar",
            "instalar",
            "buscar",
            "procurar",
            "encontrar",
            "gerar",
            "modificar",
            "editar",
            "mover",
            "copiar",
            "ler",
            "leia",
        ]

        if len(goal.split()) <= 3:
            return not any(keyword in goal for keyword in action_keywords)

        return False

    # =========================
    # 🔁 LOOP CONTROL
    # =========================
    def _should_continue(self, state):
        return not state.completed and state.iteration < self.max_iterations

    # =========================
    # 🧠 CONTEXTO
    # =========================
    def _build_context(self, goal, state):
        context = self.memory.build_context(goal, state.to_dict())
        context["session"] = self.session_context.copy()
        return context

    # =========================
    # 🔀 ROUTER
    # =========================
    def _route_if_available(self, goal, context, state):
        if not self.router:
            return "default"

        route = self.router.route(goal, context, state.to_dict())
        self._log(f"[ROUTER] -> {route}")
        state.metadata["route"] = route
        return route

    # =========================
    # 🧠 ANALYSIS
    # =========================
    def _analyze_if_available(self, goal, context):
        if hasattr(self.agent, "reasoning") and self.agent.reasoning is not None:
            analyzer = getattr(self.agent.reasoning, "analyze", None)
            if callable(analyzer):
                return analyzer(goal, context)
        return None

    # =========================
    # 🧠 PLANNER
    # =========================
    def _create_plan(self, goal, context, analysis):
        try:
            plan = self.planner.create_plan(goal, context, analysis)
            goal_type = self.planner.classify_goal(goal)
            return plan, goal_type
        except Exception:
            return None, "general"

    # =========================
    # ⚠️ VALIDAÇÃO DE PLANO
    # =========================
    def _is_invalid_plan(self, plan):
        if plan is None:
            return True
        if not isinstance(plan, list):
            return True
        if len(plan) == 0:
            return True
        return False

    def _is_direct_response(self, plan, goal_type):
        if not plan:
            return goal_type != "action"
        return False

    # =========================
    # 💬 RESPOSTA DIRETA
    # =========================
    def _handle_direct_response(self, goal, context, goal_type):
        if goal_type == "action":
            self._log("[ENGINE] Empty action plan")
            return {"status": "error", "error": "unable_to_plan_action"}

        self._log("[ENGINE] Direct response")

        try:
            output = self.agent.respond(goal, context)
            if isinstance(output, str) and output.startswith("[LLM_ERROR]"):
                return {"status": "error", "error": output}
            if isinstance(output, dict):
                return output
            return self._success(str(output).strip())
        except Exception as e:
            return self._error(str(e))

    # =========================
    # ⚙️ EXECUÇÃO
    # =========================
    def _execute_plan(self, plan, state, goal, failures):
        last_result = None

        for step in plan:
            self._log(f"[STEP] -> {step}")

            result = self._execute_step(step, state)
            last_result = result
            feedback = self.critic.evaluate(result)

            self.memory.store_step(step, result, feedback)
            state.add_history(step, result, feedback)

            if feedback == "fail":
                failures += 1
                self._log(f"[CRITIC] Fail ({failures})")

                if failures >= self.max_failures:
                    return self._too_many_failures(), failures

                break

            failures = 0

            if self.agent.check_completion(goal, state.to_dict(), result):
                self._log("[SUCCESS] Goal completed")
                state.completed = True
                return result, failures

        if last_result and last_result.get("status") == "success":
            return last_result, failures

        return last_result, failures

    # =========================
    # 🛠 EXEC STEP
    # =========================
    def _execute_step(self, step, state):
        try:
            allowed, reason = self._validate_step_security(step, state)
            if not allowed:
                return {"status": "error", "error": f"security_blocked:{reason}"}

            result = self.executor.execute(step, state.to_dict())
            if isinstance(result, dict) and result.get("status") == "success":
                data = step.get("data", {}) or {}
                path = data.get("path")
                if step.get("action") == "create_folder" and path:
                    self.session_context["last_folder_path"] = path
                if step.get("action") == "write_file" and path:
                    self.session_context["last_file_path"] = path
                    if "/" in path or "\\" in path:
                        folder = path.replace("\\", "/").rsplit("/", 1)[0]
                        if folder:
                            self.session_context["last_folder_path"] = folder
            return result
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _validate_step_security(self, step, state=None):
        if not self.guard:
            return True, None

        validator = getattr(self.guard, "validate_action", None)
        if not callable(validator):
            return True, None

        result = validator(step)

        if isinstance(result, tuple):
            if len(result) == 2:
                allowed, reason = bool(result[0]), result[1]
                if not allowed and self._is_allowed_same_plan_delete(step, state, reason):
                    return True, None
                return allowed, reason
            return bool(result[0]), None

        if isinstance(result, dict):
            return bool(result.get("allowed")), result.get("reason")

        return bool(result), None

    def _is_allowed_same_plan_delete(self, step, state, reason):
        if reason != "destructive_action_blocked:delete_file":
            return False
        if not isinstance(step, dict) or step.get("action") != "delete_file":
            return False

        data = step.get("data") or {}
        path = self._normalize_step_path(data.get("path"))
        if not path or not state:
            return False

        for entry in reversed(getattr(state, "history", [])):
            prior_step = entry.get("step", {})
            prior_result = entry.get("result", {})
            if prior_step.get("action") != "write_file":
                continue
            if isinstance(prior_result, dict) and prior_result.get("status") != "success":
                continue
            prior_path = self._normalize_step_path((prior_step.get("data") or {}).get("path"))
            if prior_path == path:
                return True

        return False

    def _normalize_step_path(self, path):
        if not isinstance(path, str) or not path.strip():
            return ""
        return path.replace("\\", "/").strip().lower()

    # =========================
    # 🧱 STATE
    # =========================
    def _init_state(self, goal):
        from core.state import AgentState

        state = AgentState(goal)
        state.metadata["workspace_root"] = self.workspace_root
        state.metadata["sandbox_root"] = self.sandbox_root or self.workspace_root
        return state

    # =========================
    # 📡 EVENTOS
    # =========================
    def _emit(self, event, data):
        if self.event_bus:
            try:
                self.event_bus.emit(event, data)
            except Exception:
                pass

    # =========================
    # ⚠️ ERROS
    # =========================
    def _handle_error(self, e):
        self._log(f"[ERROR] {e}")
        traceback.print_exc()

    def _too_many_failures(self):
        return self._error("too_many_failures")

    def _max_iterations_error(self):
        return self._error("max_iterations_reached")

    # =========================
    # ✅ HELPERS
    # =========================
    def _success(self, output):
        return {"status": "success", "output": output}

    def _error(self, msg):
        return {"status": "error", "error": msg}

    def _log(self, msg):
        if self.debug:
            self.logger.info(msg)
