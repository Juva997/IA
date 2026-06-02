__all__ = [
    "BenchmarkRunner",
    "BenchmarkLLM",
    "create_isolated_workspace",
    "compute_learning_metrics",
    "compute_metrics",
    "compute_process_metrics",
    "compute_semantic_stability",
    "compute_stability",
    "evaluate",
    "build_benchmark_engine",
    "build_benchmark_memory",
    "list_dataset_names",
    "load_dataset",
    "prepare_workspace",
    "quality_gate",
    "write_json_report",
]


def __getattr__(name):
    if name in {"evaluate"}:
        from benchmark.evaluator import evaluate

        return evaluate

    if name in {"compute_learning_metrics", "compute_metrics", "quality_gate"}:
        from benchmark.metrics import (
            compute_learning_metrics,
            compute_metrics,
            quality_gate,
        )

        return {
            "compute_learning_metrics": compute_learning_metrics,
            "compute_metrics": compute_metrics,
            "quality_gate": quality_gate,
        }[name]

    if name in {
        "compute_process_metrics",
        "compute_semantic_stability",
        "compute_stability",
    }:
        from benchmark.process_metrics import (
            compute_process_metrics,
            compute_semantic_stability,
            compute_stability,
        )

        return {
            "compute_process_metrics": compute_process_metrics,
            "compute_semantic_stability": compute_semantic_stability,
            "compute_stability": compute_stability,
        }[name]

    if name in {"BenchmarkRunner", "list_dataset_names", "load_dataset", "write_json_report"}:
        from benchmark.runner import (
            BenchmarkRunner,
            list_dataset_names,
            load_dataset,
            write_json_report,
        )

        return {
            "BenchmarkRunner": BenchmarkRunner,
            "list_dataset_names": list_dataset_names,
            "load_dataset": load_dataset,
            "write_json_report": write_json_report,
        }[name]

    if name in {
        "BenchmarkLLM",
        "build_benchmark_engine",
        "build_benchmark_memory",
        "create_isolated_workspace",
        "prepare_workspace",
    }:
        from benchmark.runtime import (
            BenchmarkLLM,
            build_benchmark_engine,
            build_benchmark_memory,
            create_isolated_workspace,
            prepare_workspace,
        )

        return {
            "BenchmarkLLM": BenchmarkLLM,
            "build_benchmark_engine": build_benchmark_engine,
            "build_benchmark_memory": build_benchmark_memory,
            "create_isolated_workspace": create_isolated_workspace,
            "prepare_workspace": prepare_workspace,
        }[name]

    raise AttributeError(name)
