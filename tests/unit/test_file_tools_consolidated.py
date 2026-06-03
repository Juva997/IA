import os
from actions.tools.file_tools import write_file, read_file, list_files


def test_write_read_and_list(tmp_path):
    state = {"workspace_root": str(tmp_path)}

    # write file with comma-separated numbers -> should calculate sum
    w = write_file({"path": "numeros.txt", "content": "1,2,3"}, state)
    assert w["status"] == "success"

    r = read_file({"path": "numeros.txt"}, state)
    assert r["status"] == "success"
    assert "Soma dos" in r["output"]

    l = list_files({"path": "."}, state)
    assert l["status"] == "success"
    assert "numeros.txt" in l["output"]


def test_read_plain_text(tmp_path):
    state = {"workspace_root": str(tmp_path)}
    write_file({"path": "hello.txt", "content": "hello world"}, state)
    r = read_file({"path": "hello.txt"}, state)
    assert r["status"] == "success"
    assert "hello world" in r["output"]
