from actions.registry import ActionRegistry
from cognition.planner import Planner


def build_planner():
    registry = ActionRegistry()
    registry.auto_register()
    from unittest.mock import Mock

    llm = Mock()
    return Planner(llm, registry)


def test_extract_inline_code():
    p = build_planner()
    code = p._extract_inline_code("execute o código: print('ola')")
    assert code.strip() == "print('ola')"


def test_plan_list_files_simple():
    p = build_planner()
    plan = p._plan_list_files("liste arquivos na pasta docs", "liste arquivos na pasta docs")
    assert plan == [{"action": "list_files", "data": {"path": "docs"}}]


def test_infer_file_extension_and_needs_session_prefix():
    p = build_planner()
    path = p._infer_file_extension("Leia-me", "arquivo txt")
    assert path == "Leia-me.txt"
    assert p._needs_session_prefix("Leia-me.txt")


def test_plan_write_file_with_session_folder_prefix():
    p = build_planner()
    plan = p._plan_write_file(
        "dentro desta pasta crie arquivo teste.txt com conteúdo Olá",
        "dentro desta pasta crie arquivo teste.txt com conteúdo Olá",
        {"last_folder_path": "sessao"},
    )
    assert plan == [{"action": "write_file", "data": {"path": "sessao/teste.txt", "content": "Olá"}}]


def test_attempt_repair_json_for_single_quotes():
    p = build_planner()
    broken = "[{'action': 'read_file', 'data': {'path': 'doc.txt'}}]"
    repaired = p._attempt_repair_json(broken)
    import json

    data = json.loads(repaired)
    assert data == [{"action": "read_file", "data": {"path": "doc.txt"}}]


def test_should_execute_python_file_and_strip_quotes_and_clean_path():
    p = build_planner()
    assert p._should_execute_python_file("main.py", "execute o arquivo main.py")
    assert p._strip_quotes("'abc'") == "abc"
    assert p._clean_path("teste dentro desta pasta algo") == "teste"
