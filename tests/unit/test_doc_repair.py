from actions.tools.doc_validator import find_doc_issues
from cognition.specialists import doc_repair


def test_doc_validator_detects_missing_docstring():
    code = """
def foo():
    return 1
"""
    issues = find_doc_issues(text=code)
    assert any("Missing" in i.message for i in issues)


def test_doc_repair_applies_and_creates_backup(tmp_path):
    p = tmp_path / "mod.py"
    p.write_text("def foo(x, y):\n    return x + y\n", encoding="utf-8")

    state = {"workspace_root": str(tmp_path)}

    res = doc_repair({"path": str(p), "run_tests": False}, state=state)
    assert res.get("status") == "success", f"doc_repair failed: {res}"

    content = p.read_text(encoding="utf-8")
    assert '"""' in content

    backup = tmp_path / (p.name + ".bak")
    assert backup.exists()
