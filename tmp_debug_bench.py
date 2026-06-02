from core.benchmark_runner import BenchmarkRunner, BenchmarkSuite
import time

class SimpleSuite(BenchmarkSuite):
    module_name = "test.simple"
    warmup_iterations = 0
    benchmark_iterations = 3

    def bench_fast_op(self):
        return sum(range(100))

    def bench_slow_op(self):
        time.sleep(0.001)
        return "done"

    def bench_failing_op(self):
        raise ValueError("Benchmark intencional de falha")

runner = BenchmarkRunner(storage_dir="tmp_bench_debug", regression_warning_pct=20.0, regression_critical_pct=50.0)
runner.register_suite(SimpleSuite())
report1 = runner.run_all(compare_baseline=False)
print("Baseline results:", [(r.name, r.mean_ms) for r in report1.results])
report2 = runner.run_all(compare_baseline=True)
print("Current results:", [(r.name, r.mean_ms) for r in report2.results])
print("Regressions:", [a.to_dict() for a in report2.regressions])
print("Has regressions:", report2.has_regressions)
