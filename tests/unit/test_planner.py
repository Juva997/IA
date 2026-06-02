from unittest.mock import Mock

from actions.registry import ActionRegistry
from cognition.planner import Planner


def build_planner():
    registry = ActionRegistry()
    registry.auto_register()
    llm = Mock()
    return Planner(llm, registry), llm


def test_planner_lists_files_without_llm():
    planner, llm = build_planner()

    plan = planner.create_plan("liste todos os arquivos na pasta atual", {})

    assert plan == [{"action": "list_files", "data": {"path": "."}}]
    llm.generate.assert_not_called()


def test_planner_writes_and_reads_file_without_llm():
    planner, llm = build_planner()

    plan = planner.create_plan("crie arquivo dados.txt com '1,2,3', leia-o", {})

    assert plan == [
        {"action": "write_file", "data": {"path": "dados.txt", "content": "1,2,3"}},
        {"action": "read_file", "data": {"path": "dados.txt"}},
    ]
    llm.generate.assert_not_called()


def test_planner_writes_file_with_portuguese_content_marker():
    planner, llm = build_planner()

    plan = planner.create_plan("criar arquivo teste.txt com conteúdo hello world", {})

    assert plan == [
        {"action": "write_file", "data": {"path": "teste.txt", "content": "hello world"}},
    ]
    llm.generate.assert_not_called()


def test_planner_creates_empty_file_with_explicit_extension():
    planner, llm = build_planner()

    plan = planner.create_plan("crie arquivo Leia-me.txt", {})

    assert plan == [{"action": "write_file", "data": {"path": "Leia-me.txt", "content": ""}}]
    llm.generate.assert_not_called()


def test_planner_infers_txt_extension_from_text_file_command():
    planner, llm = build_planner()

    plan = planner.create_plan("crie um arquivo txt chamado de Leia-me", {})

    assert plan == [{"action": "write_file", "data": {"path": "Leia-me.txt", "content": ""}}]
    llm.generate.assert_not_called()


def test_planner_creates_file_inside_newly_named_folder():
    planner, llm = build_planner()

    plan = planner.create_plan(
        "criar uma pasta chamada teste, dentro desta pasta crier um arquivo txt chamado de Leia-me",
        {},
    )

    assert plan == [
        {"action": "create_folder", "data": {"path": "teste"}},
        {"action": "write_file", "data": {"path": "teste/Leia-me.txt", "content": ""}},
    ]
    llm.generate.assert_not_called()


def test_planner_creates_file_inside_last_session_folder():
    planner, llm = build_planner()

    plan = planner.create_plan(
        "dentro desta pasta crier um arquivo txt chamado de Leia-me",
        {"session": {"last_folder_path": "teste"}},
    )

    assert plan == [{"action": "write_file", "data": {"path": "teste/Leia-me.txt", "content": ""}}]
    llm.generate.assert_not_called()


def test_planner_does_not_read_leia_hyphenated_filename():
    planner, llm = build_planner()

    plan = planner.create_plan("crie um arquivo txt chamado de Leia-me", {})

    assert plan == [{"action": "write_file", "data": {"path": "Leia-me.txt", "content": ""}}]
    llm.generate.assert_not_called()


def test_planner_runs_inline_python_without_llm():
    planner, llm = build_planner()

    plan = planner.create_plan("execute o código: print('teste')", {})

    assert plan == [{"action": "run_python", "data": {"code": "print('teste')"}}]
    llm.generate.assert_not_called()


def test_planner_creates_python_file_inside_folder_without_llm():
    planner, llm = build_planner()

    plan = planner.create_plan(
        "crie uma pasta chamada meu_projeto, dentro crie main.py com print('hello world') e execute-o",
        {},
    )

    assert plan == [
        {"action": "create_folder", "data": {"path": "meu_projeto"}},
        {
            "action": "write_file",
            "data": {"path": "meu_projeto/main.py", "content": "print('hello world')"},
        },
        {
            "action": "run_python",
            "data": {"code": "exec(open('meu_projeto/main.py').read())"},
        },
    ]
    llm.generate.assert_not_called()
