import os
import tempfile

from benchmark.repair import apply_llm_patches
from actions.registry import ActionRegistry
from actions.executor import Executor


def test_apply_txt_patch_and_py_blocked(tmp_path):
    # setup workspace with a file and a simple pytest test
    (tmp_path / "notes.txt").write_text("old\n", encoding="utf-8")
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_dummy.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")

    patch_text = "<<<PATCH\nnotes.txt\nnew content\nPATCH\n"
    applied, errors, backups = apply_llm_patches(str(tmp_path), patch_text)
    assert errors == []
    assert any(a.get("path") == "notes.txt" for a in applied)

    # python patches must be blocked by default
    patch_py = "<<<PATCH\nscript.py\nprint('hi')\nPATCH\n"
    applied2, errors2, backups2 = apply_llm_patches(str(tmp_path), patch_py)
    assert errors2, "Expected .py patches to be blocked by default"


def test_executor_apply_patch_flow_runs_pytest_in_tmpdir(tmp_path):
    # prepare minimal pytest in tmp workspace
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_dummy.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")

    patch_text = "<<<PATCH\nnotes.txt\nhello\nPATCH\n"

    registry = ActionRegistry()
    registry.auto_register()
    executor = Executor(registry)
    decision = {"action": "apply_llm_patches", "data": {"text": patch_text, "run_tests": True}}
    state = {"workspace_root": str(tmp_path)}
    result = executor.execute(decision, state)
    assert result.get("status") == "success", f"Executor flow failed: {result}"
