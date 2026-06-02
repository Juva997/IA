from unittest.mock import Mock

from actions.tools.file_tools import write_file
from core.engine import AutonomousEngine
from security.security import SecurityManager


def test_security_manager_rejects_path_outside_root(tmp_path):
    guard = SecurityManager(safe_root=str(tmp_path))

    allowed, reason = guard.validate_action(
        {"action": "write_file", "data": {"path": "../escape.txt", "content": "x"}}
    )

    assert not allowed
    assert "path_outside_safe_root" in reason


def test_engine_blocks_step_before_executor(tmp_path):
    executor = Mock()
    engine = AutonomousEngine(
        agent=Mock(),
        planner=Mock(),
        memory=Mock(),
        executor=executor,
        critic=Mock(),
        guard=SecurityManager(safe_root=str(tmp_path)),
        debug=False,
    )
    state = engine._init_state("apague arquivo")

    result = engine._execute_step(
        {"action": "delete_file", "data": {"path": "important.txt"}},
        state,
    )

    assert result["status"] == "error"
    assert result["error"].startswith("security_blocked:")
    executor.execute.assert_not_called()


def test_security_manager_allows_explicit_confirmed_delete(tmp_path):
    guard = SecurityManager(safe_root=str(tmp_path))

    allowed, reason = guard.validate_action(
        {
            "action": "delete_file",
            "data": {"path": "temp.txt", "confirm_delete": True},
        }
    )

    assert allowed
    assert reason is None


def test_file_tool_uses_explicit_workspace_root(tmp_path):
    result = write_file(
        {"path": "../escape.txt", "content": "x"},
        {"workspace_root": str(tmp_path)},
    )

    assert result["status"] == "error"
    assert "path_outside_safe_root" in result["error"]
    assert not (tmp_path.parent / "escape.txt").exists()
