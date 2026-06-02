from actions.tools.python_tools import run_python_code


def test_run_python_preserves_utf8_output(tmp_path):
    result = run_python_code(
        {"code": "print('olá')"},
        {"sandbox_root": str(tmp_path)},
    )

    assert result["status"] == "success"
    assert result["output"] == "olá"


def test_run_python_blocks_unsafe_import(tmp_path):
    result = run_python_code(
        {"code": "import os\nprint(os.getcwd())"},
        {"sandbox_root": str(tmp_path)},
    )

    assert result["status"] == "error"
    assert "import_blocked:os" in result["error"]


def test_run_python_blocks_file_escape(tmp_path):
    result = run_python_code(
        {"code": "open('../escape.txt', 'w', encoding='utf-8').write('x')"},
        {"sandbox_root": str(tmp_path)},
    )

    assert result["status"] == "error"
    assert "outside sandbox" in result["error"]


def test_run_python_executes_simple_file(tmp_path):
    script = tmp_path / "main.py"
    script.write_text("print('hello world')", encoding="utf-8")

    result = run_python_code(
        {"code": "exec(open('main.py').read())"},
        {"sandbox_root": str(tmp_path)},
    )

    assert result["status"] == "success"
    assert result["output"] == "hello world"


def test_run_python_allows_safe_workspace_file_io(tmp_path):
    result = run_python_code(
        {
            "code": (
                "open('saida.txt', 'w', encoding='utf-8').write('olá')\n"
                "print(open('saida.txt', 'r', encoding='utf-8').read())"
            )
        },
        {"sandbox_root": str(tmp_path)},
    )

    assert result["status"] == "success"
    assert result["output"] == "olá"
    assert (tmp_path / "saida.txt").read_text(encoding="utf-8") == "olá"
