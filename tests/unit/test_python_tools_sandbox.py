from actions.tools.python_tools import run_python_code, _fast_path_source


def test_run_python_in_subprocess_timeout(tmp_path):
    # Create a script that runs longer than allowed timeout
    code = "import time\ntime.sleep(2)\nprint('done')"
    res = run_python_code({"code": code, "timeout": 1}, {"sandbox_root": str(tmp_path)})
    assert res["status"] == "error"
    assert "timeout" in res["error"]


def test_fast_path_exec_reads_file(tmp_path):
    script = tmp_path / "small.py"
    script.write_text("print('fast')", encoding="utf-8")
    code = "exec(open('small.py').read())"
    source = _fast_path_source(code, str(tmp_path))
    assert source is not None


def test_run_python_defaults_to_temp_sandbox(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    res = run_python_code(
        {"code": "open('out.txt', 'w', encoding='utf-8').write('x')\nprint('ok')"}
    )

    assert res["status"] == "success"
    assert res["output"] == "ok"
    assert not (tmp_path / "out.txt").exists()
