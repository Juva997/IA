import pytest

from bootstrap.container import build_engine


def test_session_context_centralized(isolated_workspace, fake_llm):
    # use an isolated StateManager instance for test isolation
    from core.state_manager import StateManager

    sm = StateManager()
    engine = build_engine(
        llm_router=fake_llm,
        persist_path=str(isolated_workspace / "memory"),
        safe_root=str(isolated_workspace),
        debug=False,
        enable_router=False,
        state_manager=sm,
    )

    assert "session_context" in sm.session_state.metadata
    assert engine.session_context is sm.session_state.metadata["session_context"]

    engine.session_context["last_folder_path"] = "projeto"
    assert sm.session_state.metadata["session_context"]["last_folder_path"] == "projeto"


def test_snapshot_and_rollback_session_state(isolated_workspace, fake_llm):
    from core.state_manager import StateManager

    sm = StateManager()
    engine = build_engine(
        llm_router=fake_llm,
        persist_path=str(isolated_workspace / "memory"),
        safe_root=str(isolated_workspace),
        debug=False,
        enable_router=False,
        state_manager=sm,
    )

    sid1 = sm.snapshot("before", include_tasks=False)

    engine.session_context["last_folder_path"] = "abc"
    sid2 = sm.snapshot("after", include_tasks=False)

    diff = sm.diff_snapshots(sid1, sid2)
    assert diff["session"]

    sm.rollback(sid1)
    # session_context should be restored (metadata identity preserved)
    assert engine.session_context.get("last_folder_path") in (None, "")
