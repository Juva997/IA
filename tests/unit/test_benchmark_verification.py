import pytest

from benchmark.runner import BenchmarkRunner, list_dataset_names, load_dataset
from benchmark.verification import apply_setup, run_verifications


def test_apply_setup_creates_files_and_dirs(tmp_path):
    results = apply_setup(
        tmp_path,
        {
            "dirs": ["data"],
            "files": {
                "data/input.txt": "ok",
            },
        },
    )

    assert (tmp_path / "data").is_dir()
    assert (tmp_path / "data" / "input.txt").read_text(encoding="utf-8") == "ok"
    assert {result["type"] for result in results} == {"dir", "file"}


def test_apply_setup_blocks_paths_outside_workspace(tmp_path):
    with pytest.raises(ValueError, match="path_outside_workspace"):
        apply_setup(tmp_path, {"files": {"../escape.txt": "bad"}})


def test_run_verifications_supports_files_json_python_and_pytest(tmp_path):
    apply_setup(
        tmp_path,
        {
            "files": [
                {"path": "data.json", "json": {"ok": True, "count": 2}},
                {"path": "script.py", "content": "print('script_ok')\n"},
                {
                    "path": "test_sample.py",
                    "content": "def test_sample():\n    assert 2 + 2 == 4\n",
                },
            ],
        },
    )

    results = run_verifications(
        tmp_path,
        [
            {"type": "file_exists", "path": "script.py", "kind": "file"},
            {"type": "json_equals", "path": "data.json", "equals": {"ok": True, "count": 2}},
            {"type": "python_file", "path": "script.py", "stdout_contains": "script_ok"},
            {"type": "pytest", "path": "test_sample.py", "args": ["-q"], "timeout": 20},
        ],
    )

    assert len(results) == 4
    assert all(result["passed"] for result in results)


def test_runner_attaches_passing_verification_results(tmp_path):
    class FakeEngine:
        def run(self, text):
            with open("out.txt", "w", encoding="utf-8") as file:
                file.write("ok")
            return {"status": "success", "output": "ok"}

    runner = BenchmarkRunner(
        engine=FakeEngine(),
        dataset=[
            {
                "name": "verified",
                "type": "real_local",
                "input": "x",
                "verification": [
                    {"type": "file_equals", "path": "out.txt", "equals": "ok"}
                ],
                "expectations": {
                    "requires_benchmark_verification": True,
                    "verification_must_pass": True,
                    "critical_expectations": ["verification_must_pass"],
                },
            }
        ],
        runs=1,
        workspace_dir=str(tmp_path),
    )

    result = runner.run()[0]

    assert result["status"] == "success"
    assert result["runs"][0]["verification_results"][0]["passed"] is True
    assert result["metrics"]["process"]["verification_total"] == 1
    assert result["metrics"]["process"]["verification_critical_failed"] == 0


def test_runner_fails_when_critical_verification_fails(tmp_path):
    class FakeEngine:
        def run(self, text):
            return {"status": "success", "output": "ok"}

    runner = BenchmarkRunner(
        engine=FakeEngine(),
        dataset=[
            {
                "name": "verified_bad",
                "type": "real_local",
                "input": "x",
                "verification": [
                    {"type": "file_equals", "path": "missing.txt", "equals": "ok"}
                ],
            }
        ],
        runs=1,
        workspace_dir=str(tmp_path),
    )

    result = runner.run()[0]

    assert result["status"] == "error"
    assert result["runs"][0]["status"] == "error"
    assert result["runs"][0]["verification_results"][0]["passed"] is False
    assert result["metrics"]["process"]["verification_critical_failed"] == 1


def test_runner_supports_pytest_verification_case(tmp_path):
    class FakeEngine:
        def run(self, text):
            return {"status": "success", "output": "ready"}

    runner = BenchmarkRunner(
        engine=FakeEngine(),
        dataset=[
            {
                "name": "pytest_verified",
                "type": "real_local",
                "input": "x",
                "setup": {
                    "files": {
                        "calc.py": "def add(a, b):\n    return a + b\n",
                        "test_calc.py": "from calc import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n",
                    }
                },
                "verification": [
                    {"type": "pytest", "path": "test_calc.py", "args": ["-q"], "timeout": 20}
                ],
            }
        ],
        runs=1,
        workspace_dir=str(tmp_path),
    )

    result = runner.run()[0]

    assert result["status"] == "success"
    assert result["runs"][0]["verification_results"][0]["returncode"] == 0


def test_real_local_dataset_is_large_and_not_part_of_smoke_all():
    real_local = load_dataset("real_local")
    smoke_names = {test["name"] for test in load_dataset("all")}

    assert len(real_local) >= 300
    assert "real_local" in list_dataset_names()
    assert any(test["name"].startswith("real_generated_") for test in real_local)
    assert "real_file_create_exact" not in smoke_names
