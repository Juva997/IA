import benchmark.runner as runner_mod
from benchmark.repair import apply_llm_patches
from benchmark.runner import BenchmarkRunner


def test_apply_llm_patch(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    proj = ws / "swe_proj_001"
    proj.mkdir()
    (proj / "__init__.py").write_text("", encoding="utf-8")
    orig = "def add(a, b):\n    return a * b\n"
    (proj / "calc.py").write_text(orig, encoding="utf-8")

    llm_output = (
        "<<<PATCH\n"
        "swe_proj_001/calc.py\n"
        "--- original\n"
        "+++ modified\n"
        "@@\n"
        "def add(a, b):\n"
        "    return a + b\n"
        "PATCH\n\n"
        "CHANGED_FILES: ['swe_proj_001/calc.py']\n"
        "RATIONALE: corrige operador incorreto\n"
    )

    applied, errors, backups = apply_llm_patches(str(ws), llm_output)

    assert errors == []
    assert len(applied) == 1
    assert applied[0]["path"] == "swe_proj_001/calc.py"

    content = (ws / "swe_proj_001" / "calc.py").read_text(encoding="utf-8")
    assert "return a + b" in content


def test_apply_unified_diff_with_syntax_error_reverts(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    proj = ws / "swe_proj_002"
    proj.mkdir()
    (proj / "__init__.py").write_text("", encoding="utf-8")
    orig = "def add(a, b):\n    return a * b\n"
    (proj / "calc.py").write_text(orig, encoding="utf-8")

    # LLM provides a unified diff that introduces a syntax error
    llm_output = (
        "<<<PATCH\n"
        "--- a/swe_proj_002/calc.py\n"
        "+++ b/swe_proj_002/calc.py\n"
        "@@ -1,2 +1,3 @@\n"
        " def add(a, b):\n"
        "-    return a * b\n"
        "+    return a +\n"
        "PATCH\n"
    )

    applied, errors, backups = apply_llm_patches(str(ws), llm_output)

    # Expect rollback due to syntax error
    assert applied == []
    assert errors, "syntax error should be reported"
    # original content preserved
    content = (ws / "swe_proj_002" / "calc.py").read_text(encoding="utf-8")
    assert "return a * b" in content


def test_runner_rolls_back_llm_patch_when_verification_still_fails(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    proj = ws / "swe_proj_003"
    proj.mkdir()
    (proj / "__init__.py").write_text("", encoding="utf-8")
    calc = proj / "calc.py"
    original = "def add(a, b):\n    return a * b\n"
    calc.write_text(original, encoding="utf-8")

    class PatchEngine:
        def run(self, goal):
            return {
                "status": "success",
                "output": (
                    "<<<PATCH\n"
                    "--- a/swe_proj_003/calc.py\n"
                    "+++ b/swe_proj_003/calc.py\n"
                    "@@ -1,2 +1,2 @@\n"
                    " def add(a, b):\n"
                    "-    return a * b\n"
                    "+    return a - b\n"
                    "PATCH\n"
                ),
            }

    def always_fails(root, verification, sandbox=False):
        return [{"name": "pytest", "type": "pytest", "critical": True, "passed": False}]

    original_run_verifications = runner_mod.run_verifications
    runner_mod.run_verifications = always_fails
    try:
        runner = BenchmarkRunner(engine=PatchEngine(), dataset=[], repair_attempts=1)
        output = {"status": "error"}
        case = {
            "name": "rollback_failed_patch",
            "repair": True,
            "verification": [{"type": "pytest", "path": "swe_proj_003/test_calc.py"}],
        }

        runner._attach_verification_results(case, str(ws), output, engine=PatchEngine())

        assert output["status"] == "error"
        attempt = output["repair"]["attempts"][0]
        assert attempt["rolled_back"] is True
        assert "swe_proj_003/calc.py" in attempt["modified_files"]
        assert calc.read_text(encoding="utf-8") == original
    finally:
        runner_mod.run_verifications = original_run_verifications
