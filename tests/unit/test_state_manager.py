import pytest

from core.state_manager import StateManager, StateManagerError


def test_create_task_and_iteration_and_update():
    sm = StateManager()
    tid = sm.create_task(goal="Make coffee")
    st = sm.get_task_state(tid)
    assert st.goal == "Make coffee"

    it = sm.start_iteration(tid)
    assert it == 1
    it2 = sm.start_iteration(tid)
    assert it2 == 2

    sm.update_task(tid, plan=["step1", "step2"])
    st2 = sm.get_task_state(tid)
    assert st2.plan == ["step1", "step2"]


def test_token_budget_and_consumption():
    sm = StateManager(session_token_budget=100)
    tid = sm.create_task(token_budget=10)
    sm.consume_tokens(5, task_id=tid)
    assert sm.session_tokens_used == 5
    assert sm.task_tokens_used[tid] == 5

    # exceeding task budget
    with pytest.raises(StateManagerError):
        sm.consume_tokens(10, task_id=tid)

    # exceeding session budget
    with pytest.raises(StateManagerError):
        sm.consume_tokens(200)


def test_snapshot_and_rollback_and_diff():
    sm = StateManager()
    tid = sm.create_task(goal="Count")
    sm.update_task(tid, memory={"count": 1})
    sid1 = sm.snapshot("before")

    # change state
    sm.update_task(tid, memory={"count": 2})
    sid2 = sm.snapshot("after")

    diff = sm.diff_snapshots(sid1, sid2)
    assert "tasks" in diff
    assert tid in diff["tasks"]

    # rollback to before
    sm.rollback(sid1)
    st = sm.get_task_state(tid)
    assert st.memory.get("count") == 1


def test_append_tool_history_and_observations():
    sm = StateManager()
    tid = sm.create_task()
    sm.append_tool_history(tid, {"tool": "search", "query": "python"})
    st = sm.get_task_state(tid)
    assert st.tool_history and st.tool_history[0]["tool"] == "search"
    sm.record_observation(tid, {"obs": "seen"})
    assert st.observations and st.observations[0]["obs"] == "seen"
