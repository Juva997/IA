from pathlib import Path

import benchmark.runner as runner_mod
from benchmark.runner import BenchmarkRunner


def test_simulate_repair_applies_patch(tmp_path):
    # prepare workspace with a buggy add implementation
    ws = tmp_path / "ws"
    ws.mkdir()
    proj_dir = ws / "swe_proj_001"
    proj_dir.mkdir()
    (proj_dir / "__init__.py").write_text("", encoding="utf-8")
    calc_file = proj_dir / "calc.py"
    calc_file.write_text("def add(a, b):\n    return a * b\n", encoding="utf-8")
    (proj_dir / "test_calc.py").write_text(
        "from swe_proj_001.calc import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n",
        encoding="utf-8",
    )

    # fake run_verifications that checks calc.py content
    def fake_run_verifications(root, verification, sandbox=False):
        p = Path(root) / "swe_proj_001" / "calc.py"
        text = p.read_text(encoding="utf-8")
        passed = "return a + b" in text
        return [{"name": "pytest", "type": "pytest", "critical": True, "passed": passed}]

    orig_run_verifications = runner_mod.run_verifications
    runner_mod.run_verifications = fake_run_verifications

    try:
        runner = BenchmarkRunner(dataset=[], simulate_repair=True)
        output = {"status": "error"}
        test = {
            "name": "mini_swe_proj_001_fix_add",
            "verification": [{"type": "pytest", "path": "swe_proj_001/test_calc.py"}],
            "repair": True,
        }

        runner._attach_verification_results(test, str(ws), output, engine=None)

        assert output.get("repair", {}).get("success") is True
        attempts = output.get("repair", {}).get("attempts", [])
        assert len(attempts) >= 1
        first = attempts[0]
        assert "swe_proj_001/calc.py" in first.get("modified_files", [])

        # verify file content updated
        content = (ws / "swe_proj_001" / "calc.py").read_text(encoding="utf-8")
        assert "return a + b" in content
    finally:
        runner_mod.run_verifications = orig_run_verifications
