from actions.executor import Executor
from actions.registry import ActionRegistry


def test_executor_normalizes_plain_tool_result():
    registry = ActionRegistry()
    registry.register("plain", lambda data, state: "ok")
    executor = Executor(registry)

    result = executor.execute({"action": "plain", "data": {}}, {})

    assert result == {"status": "success", "output": "ok", "error": None}


def test_executor_normalizes_error_result_without_output():
    registry = ActionRegistry()
    registry.register("broken", lambda data, state: {"error": "bad"})
    executor = Executor(registry)

    result = executor.execute({"action": "broken", "data": {}}, {})

    assert result["status"] == "error"
    assert result["error"] == "bad"
    assert result["output"] is None


def test_executor_reports_unknown_tool():
    executor = Executor(ActionRegistry())

    result = executor.execute({"action": "missing", "data": {}}, {})

    assert result == {
        "status": "error",
        "output": None,
        "error": "tool_not_found: missing",
    }


def test_executor_normalizes_write_file_aliases():
    registry = ActionRegistry()
    registry.register("write_file", lambda data, state: data)
    executor = Executor(registry)

    result = executor.execute(
        {"action": "write_file", "data": {"filename": "a.txt", "content": "x"}},
        {},
    )

    assert result["status"] == "success"
    assert result["path"] == "a.txt"
    assert result["content"] == "x"


def test_executor_retries_tool_exceptions_then_errors():
    registry = ActionRegistry()
    registry.register("broken", lambda data, state: (_ for _ in ()).throw(ValueError("boom")))
    executor = Executor(registry, max_retries=1)

    result = executor.execute({"action": "broken", "data": {}}, {})

    assert result["status"] == "error"
    assert "execution_failed: boom" in result["error"]
