from actions.registry import ActionRegistry
from cognition.planner import Planner


def build_planner():
    registry = ActionRegistry()
    registry.auto_register()
    from unittest.mock import Mock

    llm = Mock()
    return Planner(llm, registry)


def test_plan_create_folder_and_file_and_execute():
    p = build_planner()
    plan = p.create_plan(
        "crie uma pasta projeto, dentro desta pasta crie main.py com print('hi') e execute-o",
        {},
    )

    assert plan[0]["action"] == "create_folder"
    assert plan[1]["action"] == "write_file"
    assert plan[2]["action"] == "run_python"


def test_plan_code_task_fatorial():
    p = build_planner()
    plan = p.create_plan("crie um fatorial", {})
    assert any(step["action"] == "write_file" and "fatorial" in step["data"]["path"] for step in plan)


def test_plan_write_and_read_csv():
    p = build_planner()
    plan = p.create_plan("crie arquivo numeros.txt com 1,2,3 e leia", {})
    assert plan[0]["action"] == "write_file"
    assert plan[1]["action"] == "read_file"


def test_extract_inline_code_variants():
    p = build_planner()
    code = p._extract_inline_code("execute o código: print(1)")
    assert code == "print(1)"
    code2 = p._extract_inline_code("rode este código: print(2)")
    assert code2 == "print(2)"
