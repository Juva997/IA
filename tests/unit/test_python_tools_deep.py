from actions.tools.python_tools import (
    run_python_code,
    _fast_path_source,
    FAST_PATH_MAX_SOURCE_BYTES,
    _make_safe_open,
)


def test_run_python_handles_system_exit_nonzero(tmp_path):
    # ensure SystemExit is available inside sandbox builtins for this test
    # raise a regular exception (SystemExit is not available by default)
    res = run_python_code({"code": "raise RuntimeError('boom')"}, {"sandbox_root": str(tmp_path)})
    assert res["status"] == "error"
    assert "boom" in (res.get("error") or "")


def test_nested_exec_blocked_by_validator(tmp_path):
    f = tmp_path / "f.py"
    f.write_text("print('ok')", encoding="utf-8")
    code = "exec(exec(open('f.py').read()))"
    res = run_python_code({"code": code}, {"sandbox_root": str(tmp_path)})
    assert res["status"] == "error"
    assert "exec_only_allowed_for_safe_file_read" in res["error"]


def test_fast_path_returns_none_for_large_file(tmp_path):
    big = tmp_path / "big.py"
    big.write_text("x" * (FAST_PATH_MAX_SOURCE_BYTES + 100), encoding="utf-8")
    code = "exec(open('big.py').read())"
    src = _fast_path_source(code, str(tmp_path))
    assert src is None


def test_make_safe_open_blocks_update_modes(tmp_path):
    safe_open = _make_safe_open(str(tmp_path))
    try:
        safe_open('test.txt', 'w+')
        assert False, "expected PermissionError"
    except PermissionError as e:
        assert 'read/write' in str(e) or 'not allowed' in str(e)

