from actions.registry import ActionRegistry
from cognition.planner import Planner


def build_planner():
    registry = ActionRegistry()
    registry.auto_register()
    from unittest.mock import Mock

    llm = Mock()
    return Planner(llm, registry)


def test_attempt_repair_json_repairs_single_quotes():
    p = build_planner()
    candidate = "[{'action': 'write_file', 'data': {'path': 'doc.txt', 'content': 'x'}}]"
    repaired = p._attempt_repair_json(candidate)
    import json

    data = json.loads(repaired)
    assert isinstance(data, list)
    assert data[0]["action"] == "write_file"
    assert data[0]["data"]["path"] == "doc.txt"
    assert data[0]["data"]["content"] == "x"


def test_normalize_python_content_fixes_main_inline():
    p = build_planner()
    src = "def f():\nprint('hi')\nif __name__ == '__main__':unittest.main()"
    normalized = p._normalize_python_content(src)
    assert "unittest.main()" in normalized
    assert "if __name__ == '__main__':\n    unittest.main()" in normalized or "if __name__ == '__main__':\n    unittest.main()" in normalized


def test_repair_plan_steps_removes_unneeded_run_after_list_files():
    p = build_planner()
    steps = [
        {"action": "list_files", "data": {"path": "."}},
        {"action": "run_python", "data": {"code": "os.listdir('.')"}},
    ]
    repaired = p._repair_plan_steps(steps, None)
    assert len(repaired) == 1
    assert repaired[0]["action"] == "list_files"


def test_repair_plan_steps_skips_run_python_when_file_not_created():
    p = build_planner()
    steps = [
        {"action": "run_python", "data": {"code": "exec(open('noexist.py').read())"}},
    ]
    repaired = p._repair_plan_steps(steps, None)
    assert repaired == []
