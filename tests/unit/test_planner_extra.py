from unittest.mock import Mock

from actions.registry import ActionRegistry
from cognition.planner import Planner


def build_planner():
    registry = ActionRegistry()
    registry.auto_register()
    llm = Mock()
    return Planner(llm, registry), llm


def test_planner_read_file_variants():
    planner, llm = build_planner()

    plan = planner.create_plan("mostrar arquivo 'doc.txt'", {})

    assert plan == [{"action": "read_file", "data": {"path": "doc.txt"}}]
    llm.generate.assert_not_called()


def test_planner_write_with_colon_and_then_read():
    planner, llm = build_planner()

    plan = planner.create_plan("criar arquivo teste.txt com conteúdo: 'hello' e depois leia", {})

    assert plan[0]["action"] == "write_file"
    assert plan[0]["data"]["path"] == "teste.txt"
    assert plan[0]["data"]["content"] == "hello"
    # deve incluir leitura
    assert any(step["action"] == "read_file" for step in plan)
    llm.generate.assert_not_called()


def test_planner_write_and_delete_combined():
    planner, llm = build_planner()

    plan = planner.create_plan("crie um arquivo temp.txt com 'x' e então delete esse arquivo", {})

    assert plan[0]["action"] == "write_file"
    assert any(step["action"] == "delete_file" for step in plan)
    llm.generate.assert_not_called()
