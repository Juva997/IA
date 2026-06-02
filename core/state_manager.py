from __future__ import annotations

import copy
import json
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class CognitiveState:
    goal: Optional[str] = None
    iteration: int = 0
    plan: List[Any] = field(default_factory=list)
    memory: Dict[str, Any] = field(default_factory=dict)
    tool_history: List[Dict[str, Any]] = field(default_factory=list)
    critic_history: List[Dict[str, Any]] = field(default_factory=list)
    failures: List[Any] = field(default_factory=list)
    observations: List[Any] = field(default_factory=list)
    workspace: Dict[str, Any] = field(default_factory=dict)
    tokens_used: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "CognitiveState":
        if d is None:
            return None
        return CognitiveState(**d)


@dataclass
class StateSnapshot:
    id: str
    timestamp: float
    session_state: Dict[str, Any]
    tasks: Dict[str, Dict[str, Any]]
    note: Optional[str] = None


class StateManagerError(Exception):
    pass


class StateManager:
    """Gerencia o estado cognitivo da sessão, tarefas e iterações.

    Recursos principais:
    - estado de sessão central (`session_state`)
    - estado por tarefa (`tasks`)
    - snapshots e rollback
    - diff entre snapshots
    - token budgeting por sessão/tarefa
    - lifecycle log básico
    """

    def __init__(self, session_id: Optional[str] = None, session_token_budget: Optional[int] = None):
        self.session_id = session_id or str(uuid.uuid4())
        self.session_state: CognitiveState = CognitiveState()
        self.tasks: Dict[str, CognitiveState] = {}
        self.closed_tasks: Dict[str, CognitiveState] = {}
        self.snapshots: Dict[str, StateSnapshot] = {}
        self.snapshot_order: List[str] = []
        self.lock = threading.RLock()
        self.lifecycle_log: List[Tuple] = []

        # Token budgeting
        self.session_token_budget: Optional[int] = session_token_budget
        self.session_tokens_used: int = 0
        self.task_token_budgets: Dict[str, Optional[int]] = {}
        self.task_tokens_used: Dict[str, int] = {}

    # ---- lifecycle / task management ----
    def create_task(self, task_id: Optional[str] = None, goal: Optional[str] = None, token_budget: Optional[int] = None) -> str:
        with self.lock:
            tid = task_id or str(uuid.uuid4())
            if tid in self.tasks or tid in self.closed_tasks:
                raise StateManagerError(f"Task {tid} already exists")
            state = CognitiveState(goal=goal)
            self.tasks[tid] = state
            self.task_token_budgets[tid] = token_budget
            self.task_tokens_used[tid] = 0
            self.lifecycle_log.append(("create_task", tid, time.time()))
            return tid

    def close_task(self, task_id: str) -> None:
        with self.lock:
            if task_id not in self.tasks:
                raise StateManagerError(f"Task {task_id} not found")
            self.closed_tasks[task_id] = self.tasks.pop(task_id)
            self.lifecycle_log.append(("close_task", task_id, time.time()))

    def get_task_state(self, task_id: str) -> CognitiveState:
        with self.lock:
            state = self.tasks.get(task_id) or self.closed_tasks.get(task_id)
            if state is None:
                raise StateManagerError(f"Task {task_id} not found")
            return state

    def start_iteration(self, task_id: str) -> int:
        with self.lock:
            st = self.get_task_state(task_id)
            st.iteration += 1
            self.lifecycle_log.append(("start_iteration", task_id, st.iteration, time.time()))
            return st.iteration

    def finish_iteration(self, task_id: str) -> None:
        with self.lock:
            st = self.get_task_state(task_id)
            self.lifecycle_log.append(("finish_iteration", task_id, st.iteration, time.time()))

    # ---- updates ----
    def update_session(self, **kwargs) -> None:
        with self.lock:
            for k, v in kwargs.items():
                if hasattr(self.session_state, k):
                    setattr(self.session_state, k, v)
                else:
                    self.session_state.metadata[k] = v
            self.lifecycle_log.append(("update_session", time.time()))

    def update_task(self, task_id: str, **kwargs) -> None:
        with self.lock:
            st = self.get_task_state(task_id)
            for k, v in kwargs.items():
                if hasattr(st, k):
                    setattr(st, k, v)
                else:
                    st.metadata[k] = v
            self.lifecycle_log.append(("update_task", task_id, time.time()))

    def append_tool_history(self, task_id: str, record: Dict[str, Any]) -> None:
        with self.lock:
            st = self.get_task_state(task_id)
            st.tool_history.append(record)
            self.lifecycle_log.append(("tool_history", task_id, time.time()))

    def record_observation(self, task_id: Optional[str], observation: Any) -> None:
        with self.lock:
            if task_id:
                st = self.get_task_state(task_id)
                st.observations.append(observation)
            else:
                self.session_state.observations.append(observation)
            self.lifecycle_log.append(("observation", task_id, time.time()))

    # ---- snapshots & rollback ----
    def snapshot(self, name: Optional[str] = None, include_tasks: bool = True, task_id: Optional[str] = None) -> str:
        with self.lock:
            snap_id = str(uuid.uuid4())
            ss = copy.deepcopy(self.session_state.to_dict())
            tasks_dict: Dict[str, Dict[str, Any]] = {}
            if include_tasks:
                if task_id:
                    t = self.tasks.get(task_id)
                    if t:
                        tasks_dict[task_id] = copy.deepcopy(t.to_dict())
                else:
                    tasks_dict = {tid: copy.deepcopy(t.to_dict()) for tid, t in self.tasks.items()}
            snap = StateSnapshot(id=snap_id, timestamp=time.time(), session_state=ss, tasks=tasks_dict, note=name)
            self.snapshots[snap_id] = snap
            self.snapshot_order.append(snap_id)
            self.lifecycle_log.append(("snapshot", snap_id, name, time.time()))
            return snap_id

    def rollback(self, snap_id: str) -> None:
        with self.lock:
            snap = self.snapshots.get(snap_id)
            if not snap:
                raise StateManagerError(f"Snapshot {snap_id} not found")
            ss_dict = copy.deepcopy(snap.session_state)
            # preserve existing session_state object to keep references (e.g. engine.session_context)
            if self.session_state is None:
                self.session_state = CognitiveState.from_dict(ss_dict)
            else:
                for k, v in ss_dict.items():
                    if k == "metadata":
                        # Update metadata keys while preserving nested dict identity
                        new_meta = v or {}
                        old_meta = self.session_state.metadata

                        # remove keys that disappeared
                        for old_k in list(old_meta.keys()):
                            if old_k not in new_meta:
                                del old_meta[old_k]

                        # update or set keys; preserve nested dict identity when possible
                        for mk, mv in new_meta.items():
                            if isinstance(mv, dict) and isinstance(old_meta.get(mk), dict):
                                old_meta[mk].clear()
                                old_meta[mk].update(mv)
                            else:
                                old_meta[mk] = mv
                    else:
                        setattr(self.session_state, k, v)

            # restore tasks mapping
            self.tasks = {tid: CognitiveState.from_dict(copy.deepcopy(ts)) for tid, ts in snap.tasks.items()}
            for tid in self.tasks.keys():
                if tid not in self.task_tokens_used:
                    self.task_tokens_used[tid] = 0
                if tid not in self.task_token_budgets:
                    self.task_token_budgets[tid] = None
            self.lifecycle_log.append(("rollback", snap_id, time.time()))

    def list_snapshots(self) -> List[str]:
        with self.lock:
            return list(self.snapshot_order)

    def diff_snapshots(self, a_id: str, b_id: str) -> Dict[str, Any]:
        with self.lock:
            a = self.snapshots.get(a_id)
            b = self.snapshots.get(b_id)
            if not a or not b:
                raise StateManagerError("snapshot not found")
            session_diff = self._dict_diff(a.session_state, b.session_state)
            task_ids = set(a.tasks.keys()) | set(b.tasks.keys())
            tasks_diff: Dict[str, Any] = {}
            for tid in task_ids:
                tasks_diff[tid] = self._dict_diff(a.tasks.get(tid), b.tasks.get(tid))
            return {"session": session_diff, "tasks": tasks_diff}

    def _dict_diff(self, a: Optional[Dict[str, Any]], b: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if a == b:
            return {}
        if a is None:
            return {"before": None, "after": b}
        if b is None:
            return {"before": a, "after": None}
        diff: Dict[str, Any] = {}
        keys = set(a.keys()) | set(b.keys())
        for k in keys:
            va = a.get(k)
            vb = b.get(k)
            if va == vb:
                continue
            if isinstance(va, dict) and isinstance(vb, dict):
                sub = self._dict_diff(va, vb)
                if sub:
                    diff[k] = sub
            else:
                diff[k] = {"before": va, "after": vb}
        return diff

    # ---- token budgeting ----
    def set_session_budget(self, budget: Optional[int]) -> None:
        with self.lock:
            self.session_token_budget = budget

    def set_task_budget(self, task_id: str, budget: Optional[int]) -> None:
        with self.lock:
            if task_id not in self.tasks and task_id not in self.closed_tasks:
                raise StateManagerError(f"Task {task_id} not found")
            self.task_token_budgets[task_id] = budget

    def consume_tokens(self, amount: int, task_id: Optional[str] = None) -> None:
        with self.lock:
            if amount < 0:
                raise StateManagerError("amount must be non-negative")
            if self.session_token_budget is not None and (self.session_tokens_used + amount) > self.session_token_budget:
                raise StateManagerError("session token budget exceeded")
            if task_id:
                if task_id not in self.tasks and task_id not in self.closed_tasks:
                    raise StateManagerError(f"Task {task_id} not found")
                tb = self.task_token_budgets.get(task_id)
                tu = self.task_tokens_used.get(task_id, 0)
                if tb is not None and (tu + amount) > tb:
                    raise StateManagerError("task token budget exceeded")
                self.task_tokens_used[task_id] = tu + amount
                st = self.get_task_state(task_id)
                st.tokens_used += amount
            self.session_tokens_used += amount
            self.session_state.tokens_used += amount
            self.lifecycle_log.append(("consume_tokens", task_id, amount, time.time()))

    def refund_tokens(self, amount: int, task_id: Optional[str] = None) -> None:
        with self.lock:
            if amount < 0:
                raise StateManagerError("amount must be non-negative")
            if task_id:
                tu = self.task_tokens_used.get(task_id, 0)
                self.task_tokens_used[task_id] = max(0, tu - amount)
                st = self.get_task_state(task_id)
                st.tokens_used = max(0, st.tokens_used - amount)
            self.session_tokens_used = max(0, self.session_tokens_used - amount)
            self.session_state.tokens_used = max(0, self.session_state.tokens_used - amount)
            self.lifecycle_log.append(("refund_tokens", task_id, amount, time.time()))

    # ---- import/export ----
    def export_state(self) -> Dict[str, Any]:
        with self.lock:
            return {
                "session_id": self.session_id,
                "session_state": copy.deepcopy(self.session_state.to_dict()),
                "tasks": {tid: copy.deepcopy(t.to_dict()) for tid, t in self.tasks.items()},
                "closed_tasks": {tid: copy.deepcopy(t.to_dict()) for tid, t in self.closed_tasks.items()},
                "snapshots": {sid: {"timestamp": s.timestamp, "session_state": copy.deepcopy(s.session_state), "tasks": copy.deepcopy(s.tasks), "note": s.note} for sid, s in self.snapshots.items()},
                "session_token_budget": self.session_token_budget,
                "session_tokens_used": self.session_tokens_used,
                "task_token_budgets": copy.deepcopy(self.task_token_budgets),
                "task_tokens_used": copy.deepcopy(self.task_tokens_used),
            }

    def import_state(self, state: Dict[str, Any]) -> None:
        with self.lock:
            self.session_id = state.get("session_id", self.session_id)
            self.session_state = CognitiveState.from_dict(copy.deepcopy(state.get("session_state", {})))
            self.tasks = {tid: CognitiveState.from_dict(copy.deepcopy(t)) for tid, t in state.get("tasks", {}).items()}
            self.closed_tasks = {tid: CognitiveState.from_dict(copy.deepcopy(t)) for tid, t in state.get("closed_tasks", {}).items()}
            self.session_token_budget = state.get("session_token_budget", self.session_token_budget)
            self.session_tokens_used = state.get("session_tokens_used", self.session_tokens_used)
            self.task_token_budgets = state.get("task_token_budgets", self.task_token_budgets)
            self.task_tokens_used = state.get("task_tokens_used", self.task_tokens_used)
            self.lifecycle_log.append(("import_state", time.time()))

    def pretty_print(self) -> str:
        return json.dumps(self.export_state(), indent=2, ensure_ascii=False)
