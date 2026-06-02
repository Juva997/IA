from actions.tools.file_tools import read_file, write_file


def test_file_tools_preserve_utf8(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    write_result = write_file({"path": "texto.txt", "content": "olá, você"})
    read_result = read_file({"path": "texto.txt"})

    assert write_result["status"] == "success"
    assert read_result["status"] == "success"
    assert read_result["output"] == "olá, você"


def test_file_tools_block_path_escape(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = write_file({"path": "../escape.txt", "content": "x"})

    assert result["status"] == "error"
    assert "path_outside_safe_root" in result["error"]
