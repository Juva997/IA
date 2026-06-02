import os
from actions.tools.file_tools import (
    write_file,
    read_file,
    delete_file,
    create_folder,
    _normalize_code_content,
    _repair_python_source,
)


def test_create_and_delete_file_success(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    res = create_folder({"path": "subdir"})
    assert res["status"] == "success"

    res = write_file({"path": "subdir/test.txt", "content": "hello"})
    assert res["status"] == "success"
    assert os.path.exists("subdir/test.txt")

    res = delete_file({"path": "subdir/test.txt"})
    assert res["status"] == "success"
    assert not os.path.exists("subdir/test.txt")


def test_write_file_missing_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    res = write_file({"content": "x"})
    assert res["status"] == "error"
    assert "path_missing" in res["error"] or res["error"] == "path_missing"


def test_read_file_sum_for_csv(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    write_file({"path": "nums.txt", "content": "1,2,3"})
    res = read_file({"path": "nums.txt"})

    assert res["status"] == "success"
    assert "Soma dos números: 6" in res["output"]


def test_write_file_sanitize_self_exec(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    write_file({"path": "secret.txt", "content": "exec(open('secret.txt').read())"})
    res = read_file({"path": "secret.txt"})

    assert res["status"] == "success"
    assert "self-exec removed" in res["output"] or res["output"].startswith("# self-exec")


def test_delete_file_not_a_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    os.makedirs("dir")
    res = delete_file({"path": "dir"})
    assert res["status"] == "error"
    assert "not_a_file" in res["error"]


def test_normalize_and_repair_helpers():
    src = "__name__ == '__main__0'\nclass A(): def method(): pass\n"
    norm = _normalize_code_content(src)
    repaired = _repair_python_source(norm)

    assert "__name__ == '__main__'" in repaired
    assert "class A" in repaired
