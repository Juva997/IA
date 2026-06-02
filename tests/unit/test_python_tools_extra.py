from actions.tools.python_tools import (
    _contains_forbidden,
    _normalize_code_text,
    _repair_python_source,
    _extract_timeout,
    _extract_exec_file_path,
    _validate_code,
)
import ast


def test_contains_forbidden():
    assert _contains_forbidden("os.system('rm -rf /')")
    assert not _contains_forbidden("print('ok')")


def test_validate_code_blocks_unsafe_import():
    result = _validate_code("import os\nprint('x')")
    assert result == "import_blocked:os"


def test_normalize_and_repair():
    src = "if __name__ == '__main__0: print('x')"
    norm = _normalize_code_text(src)
    repaired = _repair_python_source(norm)
    assert "__main__" in repaired


def test_extract_timeout():
    assert _extract_timeout({"timeout": 2}) == 2
    assert _extract_timeout({"timeout": "a"}) == 5


def test_extract_exec_file_path_valid():
    # build AST for exec(open('file').read())
    node = ast.parse("exec(open('file.py').read())")
    call = node.body[0].value
    path = _extract_exec_file_path(call)
    assert path == 'file.py'
