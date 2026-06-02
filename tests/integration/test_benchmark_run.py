import os

from benchmark.runner import BenchmarkRunner


def test_v3_default_runner_uses_common_engine_and_workspace(tmp_path):
    runner = BenchmarkRunner(
        dataset=[
            {
                "name": "default_engine_chat",
                "input": "oi",
                "type": "qa",
                "expected": "ajudar",
            }
        ],
        runs=1,
        workspace_dir=str(tmp_path),
        include_runs=True,
    )

    results = runner.run()
    workspace = os.path.abspath(results[0]["runs"][0]["workspace"])

    assert results[0]["status"] == "success"
    assert os.path.commonpath([workspace, os.path.abspath(str(tmp_path))]) == os.path.abspath(str(tmp_path))


def test_v3_runner_sequences_share_engine_memory(tmp_path):
    runner = BenchmarkRunner(
        dataset=[
            {
                "name": "memory_sequence",
                "type": "memory",
                "steps": [
                    {"input": "Me chamo Carlos", "expected": "Carlos", "type": "memory"},
                    {"input": "Qual e meu nome?", "expected": "Carlos", "type": "qa"},
                ],
            }
        ],
        runs=1,
        workspace_dir=str(tmp_path),
    )

    results = runner.run()

    assert results[0]["status"] == "success"
    assert results[0]["metrics"]["semantic_score"] == 1.0
