from core.state_manager import StateManager


# Singleton StateManager para a sessão atual
state_manager = StateManager()


class AgentState:
    """Compat layer: adaptador legacy que delega para `StateManager`.

    Mantém a API antiga (`add_history`, `last_steps`, `to_dict`, acesso a
    `iteration`, `metadata`, `completed`) enquanto persiste dados centralmente
    no `state_manager`.
    """

    def __init__(self, goal, max_history=50, task_id: str = None):
        # atributos internos começam com '_' para não colidir com delegation
        object.__setattr__(self, "_max_history", int(max_history or 50))
        if task_id:
            object.__setattr__(self, "_task_id", task_id)
        else:
            tid = state_manager.create_task(goal=goal)
            object.__setattr__(self, "_task_id", tid)

        # assegurar chaves de metadata necessárias
        st = state_manager.get_task_state(self._task_id)
        st.metadata.setdefault("history", [])
        st.metadata.setdefault("errors", [])
        st.metadata.setdefault("completed", False)

    # ---- delegation helpers ----
    @property
    def _state(self):
        return state_manager.get_task_state(self._task_id)

    # ---- legacy attributes as properties ----
    @property
    def goal(self):
        return self._state.goal

    @property
    def iteration(self):
        return self._state.iteration

    @iteration.setter
    def iteration(self, value):
        state_manager.update_task(self._task_id, iteration=int(value or 0))

    @property
    def metadata(self):
        return self._state.metadata

    @property
    def completed(self):
        return bool(self._state.metadata.get("completed", False))

    @completed.setter
    def completed(self, val: bool):
        state_manager.update_task(self._task_id, completed=bool(val))

    # ---- history helpers (legacy API) ----
    def add_history(self, step, result, feedback):
        entry = {"step": step, "result": result, "feedback": feedback}
        st = self._state
        history = list(st.metadata.get("history", []))
        history.append(entry)
        if len(history) > self._max_history:
            history.pop(0)

        errors = list(st.metadata.get("errors", []))
        if str(feedback).lower() == "fail":
            errors.append(entry)

        # Persistar via update_task (coloca chaves em metadata quando não existir)
        state_manager.update_task(self._task_id, history=history, errors=errors)

    def last_steps(self, n=5):
        return list(self._state.metadata.get("history", []))[-n:]

    def success_rate(self):
        history = list(self._state.metadata.get("history", []))
        if not history:
            return 0
        success = sum(1 for h in history if str(h.get("feedback")).lower() == "success")
        return success / len(history)

    def to_dict(self):
        st = self._state
        data = {
            "goal": st.goal,
            "history": list(st.metadata.get("history", [])),
            "iteration": st.iteration,
            "completed": bool(st.metadata.get("completed", False)),
            "errors": list(st.metadata.get("errors", [])),
            "metadata": dict(st.metadata),
            "success_rate": self.success_rate(),
        }
        data.update(st.metadata)
        return data

    # Delegate access to unknown attributes to the underlying CognitiveState
    def __getattr__(self, name):
        st = self._state
        if hasattr(st, name):
            return getattr(st, name)
        if name in st.metadata:
            return st.metadata.get(name)
        raise AttributeError(name)

    def __setattr__(self, name, value):
        # atributos internos passam sem delegação
        if name.startswith("_"):
            return object.__setattr__(self, name, value)

        # propriedades tratadas explicitamente
        if name == "iteration":
            # atualizar o campo iteration no task state
            state_manager.update_task(self._task_id, iteration=int(value or 0))
            return
        if name == "completed":
            # persisted in metadata for backward compatibility
            state_manager.update_task(self._task_id, completed=bool(value))
            return

        # atribuições genéricas vão para metadata ou atributos do state
        st = self._state
        if hasattr(st, name):
            state_manager.update_task(self._task_id, **{name: value})
        else:
            state_manager.update_task(self._task_id, **{name: value})

