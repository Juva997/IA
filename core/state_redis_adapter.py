from __future__ import annotations

import json
import os
import uuid
from typing import Any, Dict, Optional

from core.state_interface import IStateManager

try:
    import redis as _redis  # type: ignore
except Exception:
    _redis = None

from core.state_manager import CognitiveState, StateManager, StateManagerError


class StateRedisAdapter(IStateManager):
    """Adaptador simples para persistir estado em Redis com fallback para memória.

    Esta implementação é propositalmente conservadora: quando o cliente Redis
    não estiver disponível o adaptador delega para um `StateManager` em memória.
    Objetivo inicial: fornecer um ponto de extensão e um switch por config/env.
    """

    def __init__(self, redis_url: Optional[str] = None, fallback_to_memory: bool = True):
        self.redis_url = redis_url or os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        self._redis = None
        self._fallback: Optional[StateManager] = None

        if _redis:
            try:
                self._redis = _redis.Redis.from_url(self.redis_url, decode_responses=True)
                # quick ping to validate connection
                self._redis.ping()
            except Exception:
                self._redis = None

        if self._redis is None and fallback_to_memory:
            self._fallback = StateManager()

    def _task_key(self, tid: str) -> str:
        return f"state:task:{tid}"

    def _tasks_set_key(self) -> str:
        return "state:tasks"

    # ---- basic delegation if redis unavailable ----
    def create_task(self, task_id: Optional[str] = None, goal: Optional[str] = None, token_budget: Optional[int] = None) -> str:
        if self._fallback:
            return self._fallback.create_task(task_id=task_id, goal=goal, token_budget=token_budget)

        tid = task_id or str(uuid.uuid4())
        st = CognitiveState(goal=goal)
        st.metadata.setdefault("history", [])
        st.metadata.setdefault("errors", [])
        st.metadata.setdefault("completed", False)

        self._redis.set(self._task_key(tid), json.dumps(st.to_dict(), ensure_ascii=False))
        try:
            self._redis.sadd(self._tasks_set_key(), tid)
        except Exception:
            pass

        if token_budget is not None:
            try:
                self._redis.hset("state:task_budgets", tid, int(token_budget))
            except Exception:
                pass

        return tid

    def close_task(self, task_id: str) -> None:
        if self._fallback:
            return self._fallback.close_task(task_id)
        val = self._redis.get(self._task_key(task_id))
        if val:
            self._redis.hset("state:closed_tasks", task_id, val)
            try:
                self._redis.srem(self._tasks_set_key(), task_id)
            except Exception:
                pass
            try:
                self._redis.delete(self._task_key(task_id))
            except Exception:
                pass

    def get_task_state(self, task_id: str) -> Any:
        if self._fallback:
            return self._fallback.get_task_state(task_id)
        val = self._redis.get(self._task_key(task_id))
        if not val:
            raise StateManagerError(f"Task {task_id} not found")
        data = json.loads(val)
        return CognitiveState.from_dict(data)

    def update_task(self, task_id: str, **kwargs) -> None:
        if self._fallback:
            return self._fallback.update_task(task_id, **kwargs)
        st = self.get_task_state(task_id)
        for k, v in kwargs.items():
            if hasattr(st, k):
                setattr(st, k, v)
            else:
                st.metadata[k] = v
        self._redis.set(self._task_key(task_id), json.dumps(st.to_dict(), ensure_ascii=False))

    def start_iteration(self, task_id: str) -> int:
        if self._fallback:
            return self._fallback.start_iteration(task_id)
        st = self.get_task_state(task_id)
        st.iteration += 1
        self._redis.set(self._task_key(task_id), json.dumps(st.to_dict(), ensure_ascii=False))
        return st.iteration

    def finish_iteration(self, task_id: str) -> None:
        if self._fallback:
            return self._fallback.finish_iteration(task_id)
        # noop for redis adapter
        return None

    def update_session(self, **kwargs) -> None:
        if self._fallback:
            return self._fallback.update_session(**kwargs)
        sess = {}
        val = self._redis.get("state:session")
        if val:
            try:
                sess = json.loads(val)
            except Exception:
                sess = {}
        sess.update(kwargs or {})
        self._redis.set("state:session", json.dumps(sess, ensure_ascii=False))

    def set_session_budget(self, budget: Optional[int]) -> None:
        if self._fallback:
            return self._fallback.set_session_budget(budget)
        if budget is None:
            try:
                self._redis.hdel("state:meta", "session_token_budget")
            except Exception:
                pass
        else:
            try:
                self._redis.hset("state:meta", "session_token_budget", int(budget))
            except Exception:
                pass

    def export_state(self) -> Dict[str, Any]:
        if self._fallback:
            return self._fallback.export_state()
        tasks: Dict[str, Any] = {}
        try:
            tids = list(self._redis.smembers(self._tasks_set_key()) or [])
        except Exception:
            tids = []
        for tid in tids:
            v = self._redis.get(self._task_key(tid))
            if v:
                try:
                    tasks[tid] = json.loads(v)
                except Exception:
                    tasks[tid] = v

        session = {}
        val = self._redis.get("state:session")
        if val:
            try:
                session = json.loads(val)
            except Exception:
                session = {}

        meta = {}
        try:
            meta = dict(self._redis.hgetall("state:meta") or {})
        except Exception:
            meta = {}

        return {"session_state": session, "tasks": tasks, "meta": meta}

    def import_state(self, state: Dict[str, Any]) -> None:
        if self._fallback:
            return self._fallback.import_state(state)
        if not isinstance(state, dict):
            return
        session = state.get("session_state", {})
        try:
            self._redis.set("state:session", json.dumps(session, ensure_ascii=False))
        except Exception:
            pass
        tasks = state.get("tasks", {}) or {}
        for tid, tdata in tasks.items():
            try:
                self._redis.set(self._task_key(tid), json.dumps(tdata, ensure_ascii=False))
                self._redis.sadd(self._tasks_set_key(), tid)
            except Exception:
                pass

    def pretty_print(self) -> str:
        try:
            return json.dumps(self.export_state(), indent=2, ensure_ascii=False)
        except Exception:
            return "{}"
