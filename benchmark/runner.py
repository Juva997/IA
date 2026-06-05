import argparse
import inspect
import re
import json
import os
import platform
import shutil
import sys
import time
import hashlib
import difflib
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

from benchmark.evaluator import evaluate
from benchmark.metrics import compute_metrics, quality_gate
from benchmark.process_metrics import compute_process_metrics
from benchmark.repair import (
    apply_llm_patches as _apply_llm_patches,
    read_workspace_texts as _read_workspace_texts,
    rollback_patches as _rollback_patches,
)
from benchmark.real_local import load_real_local_dataset
from benchmark.runtime import build_benchmark_engine, prepare_workspace
from benchmark.validators.common import normalize_record
from benchmark.validators.process import compute_efficiency_factor
from benchmark.verification import (
    apply_setup,
    critical_verifications_passed,
    run_verifications,
    verification_summary,
)


DATASET_DIR = Path(__file__).resolve().parent / "datasets"
LARGE_DATASETS = {"real_local", "mini_swe"}
OPTIONAL_DATASETS = {"e2e_optional", "llm", "slow"}
FULL_DATASET_ALIASES = {"full", "complete", "all_full"}
OPTIONAL_DATASET_ALIASES = {"optional", "llm_slow_e2e", "external_optional"}
DATASET_NAME_ALIASES = {
    "llm_external": "llm",
    "slow_optional": "slow",
}


class BenchmarkRunner:
    def __init__(
        self,
        engine=None,
        engine_factory=None,
        dataset=None,
        runs=3,
        workspace_dir=None,
        keep_workspaces=False,
        use_external_llm=False,
        include_runs=True,
        verbose=False,
        min_score=0.75,
        sandbox=False,
        enable_repair=True,
        repair_attempts=2,
        simulate_repair=False,
        llm_judge=None,
    ):
        self.engine = engine
        self.engine_factory = engine_factory
        self.dataset = dataset or []
        self.runs = max(1, int(runs or 1))
        self.workspace_dir = workspace_dir
        self.keep_workspaces = keep_workspaces
        self.use_external_llm = use_external_llm
        self.dataset = _filter_external_llm_cases(self.dataset, self.use_external_llm)
        self.include_runs = include_runs
        self.verbose = verbose
        self.min_score = float(min_score)
        self.sandbox = bool(sandbox)
        self.enable_repair = bool(enable_repair)
        self.repair_attempts = int(repair_attempts)
        self.simulate_repair = bool(simulate_repair)
        self.llm_judge = llm_judge

    def run(self):
        wall_started = time.perf_counter()
        results = []

        for test in self.dataset:
            outputs = []
            times = []

            for run_number in range(1, self.runs + 1):
                run = self._run_test_once(test, run_number)
                outputs.append(run["output"])
                times.append(run["time"])

            evaluation = evaluate(test, outputs, llm_judge=self.llm_judge)
            process_metrics = compute_process_metrics(outputs)
            process_metrics["efficiency_factor"] = compute_efficiency_factor(
                test.get("expectations") if isinstance(test, dict) else {},
                process_metrics,
            )
            metrics = compute_metrics(
                outputs,
                times,
                evaluation,
                process_metrics=process_metrics,
            )
            passed = self._passes_quality_thresholds(test, evaluation, metrics)

            result = {
                "name": test.get("name", "unnamed"),
                "type": test.get("type", "unknown"),
                "status": "success" if passed else "error",
                "evaluation": evaluation,
                "metrics": metrics,
            }
            if self.include_runs:
                result["runs"] = outputs

            results.append(result)

        self.last_wall_time_s = time.perf_counter() - wall_started
        return results

    def _passes_quality_thresholds(self, test, evaluation, metrics):
        process = metrics.get("process", {}) or {}
        if int(process.get("verification_critical_failed", 0) or 0) > 0:
            return False

        if metrics["final_score"] < float(test.get("min_score", self.min_score)):
            return False

        if test.get("format"):
            min_format_score = float(test.get("min_format_score", 1.0))
            if evaluation.get("format", 0.0) < min_format_score:
                return False

        min_semantic_score = test.get("min_semantic_score")
        if min_semantic_score is not None:
            if evaluation.get("semantic", 0.0) < float(min_semantic_score):
                return False

        min_rubric_score = test.get("min_rubric_score")
        if min_rubric_score is not None:
            if evaluation.get("rubric", 1.0) < float(min_rubric_score):
                return False

        min_judge_score = test.get("min_judge_score")
        if min_judge_score is not None and self.llm_judge is not None:
            if evaluation.get("judge") is None:
                return False
            if evaluation.get("judge", 0.0) < float(min_judge_score):
                return False

        if test.get("expectations"):
            min_process_score = float(test.get("min_process_score", 1.0))
            if evaluation.get("process", 0.0) < min_process_score:
                return False

        return True

    def _run_test_once(self, test, run_number):
        original_dir = os.getcwd()
        root = os.path.abspath(
            prepare_workspace(self.workspace_dir, prefix="ia_benchmark_")
        )
        start = time.perf_counter()
        setup_results = []

        try:
            os.chdir(root)
            setup_results = apply_setup(root, test.get("setup"))
            engine = self._build_engine(root)

            if self.verbose:
                output = self._run_test_payload(engine, test)
            else:
                stdout = StringIO()
                stderr = StringIO()
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    output = self._run_test_payload(engine, test)

            output["setup_results"] = setup_results
            self._attach_verification_results(test, root, output, engine=engine)
        except Exception as exc:
            output = {
                "status": "error",
                "output": str(exc),
                "error": str(exc),
                "raw": {"status": "error", "error": str(exc)},
                "setup_results": setup_results,
                "verification_results": [],
                "verification_summary": verification_summary([]),
            }
        finally:
            elapsed = time.perf_counter() - start

            if not isinstance(output, dict):
                output = normalize_record(output)

            output["run"] = run_number
            output["workspace"] = root
            output["workspace_files"] = _snapshot_workspace(root)
            output["workspace_artifacts"] = _snapshot_workspace_artifacts(root)
            os.chdir(original_dir)
            if not self.keep_workspaces:
                shutil.rmtree(root, ignore_errors=True)
        return {"time": elapsed, "output": output}

    def _run_test_payload(self, engine, test):
        # Special case: doc_repair tests use the doc_repair specialist to modify files
        if test.get("type") == "doc_repair":
            try:
                # current working directory is the workspace root
                root = os.getcwd()
                # dynamic import to avoid startup import cycles
                from cognition.specialists import doc_repair

                setup = test.get("setup") or {}
                files = []
                if isinstance(setup, dict):
                    fs = setup.get("files") or []
                    if isinstance(fs, dict):
                        files = list(fs.keys())
                    elif isinstance(fs, list):
                        files = [s.get("path") for s in fs if isinstance(s, dict) and s.get("path")]

                results = []
                for f in files:
                    try:
                        state = {"workspace_root": root}
                        # run_tests=False to let runner handle verification
                        r = doc_repair({"path": f, "run_tests": False}, state=state)
                    except Exception as exc:
                        r = {"status": "error", "error": str(exc)}
                    results.append({"path": f, "result": r})

                status = "success" if all(r.get("result", {}).get("status") == "success" for r in results) else "error"
                return {"status": status, "output": results}
            except Exception as exc:
                return {"status": "error", "output": None, "error": str(exc)}

        if isinstance(test.get("steps"), list):
            records = []
            for step in test["steps"]:
                # PoC: se fila habilitada, enfileirar engine.run em vez de executar localmente
                try:
                    from integrations.queue_client import enqueue_engine_run
                except Exception:
                    enqueue_engine_run = None

                if enqueue_engine_run and (os.environ.get("ASSISTENTE_QUEUE_DRIVER") or os.environ.get("QUEUE_DRIVER")):
                    job = enqueue_engine_run(step.get("input", ""), workspace_root=os.getcwd())
                    if job is not None:
                        records.append({"status": "queued", "output": None, "error": None, "job_id": job.get_id()})
                        continue

                response = engine.run(step.get("input", ""))
                records.append(normalize_record(response))

            status = "success" if records and all(r.get("status") == "success" for r in records) else "error"
            return {
                "status": status,
                "output": records[-1].get("output") if records else "",
                "error": _first_error(records),
                "steps": records,
            }

        try:
            from integrations.queue_client import enqueue_engine_run
        except Exception:
            enqueue_engine_run = None

        if enqueue_engine_run and (os.environ.get("ASSISTENTE_QUEUE_DRIVER") or os.environ.get("QUEUE_DRIVER")):
            job = enqueue_engine_run(test.get("input", ""), workspace_root=os.getcwd())
            if job is not None:
                return normalize_record({"status": "queued", "output": None, "error": None, "job_id": job.get_id()})

        response = engine.run(test.get("input", ""))
        return normalize_record(response)

    def _attach_verification_results(self, test, root, output, engine=None):
        verification_results = run_verifications(root, test.get("verification"), sandbox=self.sandbox)
        output["verification_results"] = verification_results
        output["verification_summary"] = verification_summary(verification_results)

        if verification_results and not critical_verifications_passed(verification_results):
            output["status"] = "error"
            failed = [
                result.get("name", result.get("type", "verification"))
                for result in verification_results
                if result.get("critical", True) and not result.get("passed")
            ]
            message = "verification_failed:" + ",".join(failed)
            output["error"] = message
            output["verification_error"] = message

            # Automatic repair flow for mini-SWE style cases
            repair_enabled_for_case = bool(test.get("repair", False)) and self.enable_repair and (
                engine is not None or self.simulate_repair
            )
            if repair_enabled_for_case:
                attempts_allowed = int(test.get("repair_attempts", self.repair_attempts) or self.repair_attempts)
                output.setdefault("attempts", [])
                output.setdefault("repair", {"attempts": [], "success": False})

                # find pytest checks to reference
                pytest_checks = [c for c in (test.get("verification") or []) if isinstance(c, dict) and (c.get("type") == "pytest" or c.get("check") == "pytest")]

                for attempt_no in range(1, attempts_allowed + 1):
                    # build repair goal with richer guidance
                    tests_list = [str(c.get("path") or c.get("paths") or "") for c in pytest_checks]
                    tests_list = [t for t in tests_list if t]
                    tests_desc = ", ".join(tests_list) if tests_list else "os testes"
                    tests_command = f"python -m pytest {' '.join(tests_list)}" if tests_list else "python -m pytest"

                    workspace_files = _snapshot_workspace(root)
                    workspace_hint = ", ".join(workspace_files[:50]) + ("..." if len(workspace_files) > 50 else "")

                    goal = (
                        "Você é um agente de reparo de código. Objetivo: modificar apenas arquivos dentro do workspace atual "
                        f"para que {tests_desc} passem quando executados com `{tests_command}`.\n\n"
                        "Restrições importantes:\n"
                        "- NÃO altere arquivos fora do workspace.\n"
                        "- NÃO instale dependências, NÃO faça chamadas de rede externas.\n"
                        "- Mantenha as mudanças o mais pequenas e localizadas possível.\n"
                        "- NÃO remova testes; altere-os apenas se for absolutamente necessário e explique por quê.\n"
                        "- NÃO modifique `config.json`.\n\n"
                        "Como entregar as mudanças (formato obrigatório):\n"
                        "Para cada arquivo modificado, inclua um patch unificado com o seguinte formato exato:\n"
                        "<<<PATCH\n"
                        "path/to/file.py\n"
                        "--- original\n"
                        "+++ modified\n"
                        "@@\n"
                        "<conteúdo completo do arquivo modificado (apenas o novo conteúdo é aceitável)>\n"
                        "PATCH\n\n"
                        "Além disso, no final da sua resposta inclua um resumo em português com:\n"
                        "- CHANGED_FILES: lista de arquivos alterados\n"
                        "- RATIONALE: explicação curta por arquivo (1-2 linhas)\n"
                        "- TEST_COMMAND: exatamente o comando a ser executado para validar (ex: `{tests_command}`)\n\n"
                        "Contexto: os principais arquivos visíveis no workspace são: " + workspace_hint + "\n\n"
                        "A meta final: após suas mudanças, os testes acima devem passar quando o runner executar pytest."
                        )
                    # If an engine is available, request patches in the required format
                    if engine is not None:
                        try:
                            if self.verbose:
                                response = engine.run(goal)
                            else:
                                stdout = StringIO()
                                stderr = StringIO()
                                with redirect_stdout(stdout), redirect_stderr(stderr):
                                    response = engine.run(goal)
                        except Exception as exc:
                            response = {"status": "error", "error": str(exc)}

                        record = normalize_record(response)
                        raw_output = record.get("output", "")

                        if isinstance(raw_output, str) and "<<<PATCH" in raw_output:
                            applied, errors, backups = _apply_llm_patches(root, raw_output)

                            after_results = run_verifications(root, test.get("verification"), sandbox=self.sandbox)
                            after_summary = verification_summary(after_results)

                            # if verifications pass after applying patches, keep changes
                            if after_summary.get("ok"):
                                output["verification_results"] = after_results
                                output["verification_summary"] = after_summary
                                attempt_entry = {
                                    "attempt": attempt_no,
                                    "engine_result": record,
                                    "verification_results": after_results,
                                    "verification_summary": after_summary,
                                    "modified_files": [p["path"] for p in applied],
                                    "patches": applied,
                                    "errors": errors,
                                    "backups": backups,
                                    "rolled_back": False,
                                }

                                output.setdefault("attempts", []).append(attempt_entry)
                                output.setdefault("repair", {"attempts": [], "success": False})
                                output["repair"]["attempts"].append(attempt_entry)

                                output["status"] = "success"
                                output["error"] = None
                                output.pop("verification_error", None)
                                output["repair"]["success"] = True
                                break

                            # otherwise revert changes and record rollback info
                            rollback_errors = []
                            try:
                                rollback_errors = _rollback_patches(root, backups)
                            except Exception as exc:
                                rollback_errors = [{"error": str(exc)}]

                            attempt_entry = {
                                "attempt": attempt_no,
                                "engine_result": record,
                                "verification_results": after_results,
                                "verification_summary": after_summary,
                                "modified_files": [p["path"] for p in applied],
                                "patches": applied,
                                "errors": errors,
                                "backups": backups,
                                "rolled_back": True,
                                "rollback_errors": rollback_errors,
                            }

                            output.setdefault("attempts", []).append(attempt_entry)
                            output.setdefault("repair", {"attempts": [], "success": False})
                            output["repair"]["attempts"].append(attempt_entry)

                            if not self.simulate_repair:
                                continue
                        else:
                            # No patches in LLM reply; record the engine result so we can inspect later
                            attempt_entry = {
                                "attempt": attempt_no,
                                "engine_result": record,
                                "modified_files": [],
                                "patches": [],
                            }
                            output.setdefault("attempts", []).append(attempt_entry)
                            output.setdefault("repair", {"attempts": [], "success": False})
                            output["repair"]["attempts"].append(attempt_entry)
                            if not self.simulate_repair:
                                continue

                    # Simulation mode: apply simple heuristic patches locally (useful for mini_swe)
                    if self.simulate_repair:
                        pre_texts = _read_workspace_texts(root)
                        patches = []
                        modified_files = []

                        for rel, content in pre_texts.items():
                            # target simple project files named calc.py
                            if not rel.endswith("calc.py"):
                                continue

                            original = content
                            lines = original.splitlines(keepends=True)
                            new_lines = []
                            in_def = False
                            replaced = False

                            for line in lines:
                                stripped = line.lstrip()
                                if not in_def and re.match(r"def\s+add\s*\(", line.strip()):
                                    in_def = True
                                    new_lines.append(line)
                                    continue
                                if in_def and not replaced:
                                    if stripped.startswith("return"):
                                        cur_indent = line[: len(line) - len(stripped)]
                                        new_lines.append(cur_indent + "return a + b\n")
                                        replaced = True
                                        continue
                                    new_lines.append(line)
                                    continue
                                new_lines.append(line)

                            if in_def and not replaced:
                                for idx, candidate_line in enumerate(new_lines):
                                    if re.match(r"def\s+add\s*\(", candidate_line.strip()):
                                        insert_at = idx + 1
                                        break
                                else:
                                    insert_at = None
                                if insert_at is not None:
                                    new_lines.insert(insert_at, "    return a + b\n")
                                    replaced = True

                            new_text = "".join(new_lines)
                            if original != new_text:
                                target_path = Path(root) / rel
                                target_path.parent.mkdir(parents=True, exist_ok=True)
                                try:
                                    target_path.write_text(new_text, encoding="utf-8")
                                except Exception:
                                    # skip files we can't write
                                    continue

                                diff = "".join(
                                    difflib.unified_diff(
                                        original.splitlines(keepends=True),
                                        new_text.splitlines(keepends=True),
                                        fromfile=f"a/{rel}",
                                        tofile=f"b/{rel}",
                                    )
                                )
                                patches.append({"path": rel, "diff": diff})
                                modified_files.append(rel)

                        after_results = run_verifications(root, test.get("verification"), sandbox=self.sandbox)
                        after_summary = verification_summary(after_results)

                        attempt_entry = {
                            "attempt": attempt_no,
                            "engine_result": {"status": "simulated", "note": "heuristic patch applied (return a + b)"},
                            "verification_results": after_results,
                            "verification_summary": after_summary,
                            "modified_files": modified_files,
                            "patches": patches,
                        }

                        output.setdefault("attempts", []).append(attempt_entry)
                        output.setdefault("repair", {"attempts": [], "success": False})
                        output["repair"]["attempts"].append(attempt_entry)

                        if after_summary.get("ok"):
                            output["verification_results"] = after_results
                            output["verification_summary"] = after_summary
                            output["status"] = "success"
                            output["error"] = None
                            output.pop("verification_error", None)
                            output["repair"]["success"] = True
                            break
                        # otherwise continue attempts loop (if multiple attempts configured)
                        continue

    def _build_engine(self, root):
        if self.engine_factory is not None:
            return _call_factory(self.engine_factory, root)

        if self.engine is not None:
            return self.engine

        return _default_engine_factory(
            root,
            use_external_llm=self.use_external_llm,
            verbose=self.verbose,
        )


def load_dataset(name_or_path="all"):
    if isinstance(name_or_path, (list, tuple)):
        dataset = []
        for item in name_or_path:
            dataset.extend(load_dataset(item))
        return dataset

    normalized_name = str(name_or_path).replace("-", "_")
    normalized_name = DATASET_NAME_ALIASES.get(normalized_name, normalized_name)

    if normalized_name in FULL_DATASET_ALIASES:
        return load_dataset(["all", *sorted(LARGE_DATASETS)])

    if normalized_name in OPTIONAL_DATASET_ALIASES:
        return load_dataset(sorted(OPTIONAL_DATASETS))

    if name_or_path in (None, "", "all"):
        dataset = []
        for path in sorted(DATASET_DIR.glob("*.json")):
            if path.stem in LARGE_DATASETS or path.stem in OPTIONAL_DATASETS:
                continue
            dataset.extend(_read_dataset_file(path))
        return dataset

    if normalized_name == "real_local":
        return load_real_local_dataset()

    dataset_candidate = DATASET_DIR / f"{normalized_name}.json"
    candidate = Path(str(name_or_path))
    if dataset_candidate.exists() and not candidate.is_file():
        candidate = dataset_candidate
    elif not candidate.exists():
        candidate = dataset_candidate

    return _read_dataset_file(candidate)


def write_json_report(results, output_path, meta=None):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    meta = dict(meta or {})
    if "generated_at" not in meta:
        meta["generated_at"] = datetime.now(timezone.utc).isoformat()
    report = {
        "meta": meta,
        "summary": {
            "total": len(results),
            "passed": sum(1 for r in results if r.get("status") == "success"),
            "failed": sum(1 for r in results if r.get("status") != "success"),
            "quality_gate": quality_gate(results),
        },
        "results": results,
    }
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(output_path)


def _read_dataset_file(path):
    path = Path(path)
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if isinstance(data, dict):
        data = data.get("tests", [])

    if not isinstance(data, list):
        raise ValueError(f"dataset must be a list: {path}")

    return data


def _filter_external_llm_cases(dataset, use_external_llm=False):
    dataset = list(dataset or [])
    if use_external_llm:
        return dataset
    return [test for test in dataset if not _requires_external_llm(test)]


def _requires_external_llm(test):
    if not isinstance(test, dict):
        return False
    if bool(test.get("requires_external_llm")):
        return True
    tags = test.get("tags") or []
    return "external_llm" in tags or "ollama" in tags


def list_dataset_names():
    names = {path.stem for path in DATASET_DIR.glob("*.json")}
    names.add("real_local")
    names.add("full")
    names.add("optional")
    return sorted(names)


def _call_factory(factory, root):
    try:
        signature = inspect.signature(factory)
    except (TypeError, ValueError):
        return factory(root)

    params = signature.parameters
    accepts_args = any(
        param.kind == inspect.Parameter.VAR_POSITIONAL
        for param in params.values()
    )
    accepts_kwargs = any(
        param.kind == inspect.Parameter.VAR_KEYWORD
        for param in params.values()
    )

    if accepts_args or accepts_kwargs or len(params) >= 1:
        return factory(root)
    return factory()


def _default_engine_factory(root, use_external_llm=False, verbose=False):
    return build_benchmark_engine(
        root,
        use_external_llm=use_external_llm,
        verbose=verbose,
        enable_router=False,
    )


def _default_llm_judge():
    from integrations.llm_client import LLMClient
    from utils.config_loader import ConfigLoader

    config = ConfigLoader()
    return LLMClient(
        model=config.get("llm.default_model", "qwen2.5:3b"),
        base_url=config.get("llm.base_url", "http://localhost:11434/api/generate"),
        timeout=float(config.get("llm.timeout", 15)),
        cache_ttl=int(config.get("llm.cache_ttl", 120)),
        max_retries=int(config.get("llm.max_retries", 0)),
        retry_delay=float(config.get("llm.retry_delay", 0.2)),
    )


def _first_error(records):
    for record in records:
        if record.get("error"):
            return record["error"]
    return None


def _snapshot_workspace(root):
    files = []
    root_path = Path(root)
    for path in root_path.rglob("*"):
        if path.is_file():
            files.append(path.relative_to(root_path).as_posix())
    return sorted(files)


def _snapshot_workspace_artifacts(root, max_text_bytes=8192):
    artifacts = {}
    root_path = Path(root)
    for path in root_path.rglob("*"):
        if not path.is_file():
            continue

        relative = path.relative_to(root_path).as_posix()
        try:
            data = path.read_bytes()
        except OSError:
            continue

        metadata = {
            "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
        if len(data) <= max_text_bytes:
            try:
                metadata["text"] = data.decode("utf-8")
            except UnicodeDecodeError:
                metadata["binary"] = True

        artifacts[relative] = metadata
    return artifacts


def _main(argv=None):
    parser = argparse.ArgumentParser(
        description="Benchmark V3 runner",
        epilog="Exit code 1 if any case fails (unless --allow-failures).",
    )
    parser.add_argument(
        "--dataset",
        default="all",
        help="dataset name, path, all (smoke), full (all + large), or optional (llm + slow + e2e_optional)",
    )
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--workspace-dir", default=None)
    parser.add_argument("--json", dest="json_report", default=None)
    parser.add_argument("--external-llm", action="store_true")
    parser.add_argument(
        "--llm-judge",
        action="store_true",
        help="enable local LLM-as-a-judge for cases marked with llm_judge/judge",
    )
    parser.add_argument("--sandbox", action="store_true", help="execute verifications with a sanitized subprocess environment")
    parser.add_argument("--keep-workspaces", action="store_true")
    parser.add_argument("--allow-failures", action="store_true")
    parser.add_argument("--min-score", type=float, default=0.75)
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument(
        "--simulate-repair",
        action="store_true",
        help="simulate auto-apply repair patches heuristically (useful for mini_swe)",
    )
    parser.add_argument(
        "--list-datasets",
        action="store_true",
        help="print built-in dataset names (JSON stems) and exit",
    )
    args = parser.parse_args(argv)

    if args.list_datasets:
        for name in list_dataset_names():
            print(name, flush=True)
        return 0

    dataset = load_dataset(args.dataset)
    llm_judge = _default_llm_judge() if args.llm_judge else None
    runner = BenchmarkRunner(
        dataset=dataset,
        runs=args.runs,
        workspace_dir=args.workspace_dir,
        keep_workspaces=args.keep_workspaces,
        use_external_llm=args.external_llm,
        verbose=not args.quiet,
        sandbox=args.sandbox,
        min_score=args.min_score,
        simulate_repair=args.simulate_repair,
        llm_judge=llm_judge,
    )
    results = runner.run()

    report_meta = {
        "dataset": args.dataset,
        "runs_per_test": args.runs,
        "wall_time_s": round(getattr(runner, "last_wall_time_s", 0.0) or 0.0, 6),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "llm_judge": bool(args.llm_judge),
    }

    if args.json_report:
        path = write_json_report(results, args.json_report, meta=report_meta)
        if not args.quiet:
            print(f"[V3] JSON salvo em: {path}", flush=True)

    if not args.quiet:
        _print_summary(results, wall_time_s=report_meta["wall_time_s"])

    if args.allow_failures:
        return 0
    return 0 if all(r["status"] == "success" for r in results) else 1


def _print_summary(results, wall_time_s=None):
    passed = sum(1 for r in results if r.get("status") == "success")
    total = len(results)
    print("\nBENCHMARK V3", flush=True)
    if wall_time_s is not None:
        print(f"cases={total}  passed={passed}  wall={wall_time_s:.3f}s", flush=True)
    print("-" * 80, flush=True)
    for result in results:
        metrics = result["metrics"]
        stdev = metrics.get("latency_stdev") or 0.0
        quality_parts = [
            f"semantic={metrics['semantic_score']:.2f}",
            f"format={metrics['format_score']:.2f}",
            f"consistency={metrics['consistency_score']:.2f}",
        ]
        if "rubric_score" in metrics:
            quality_parts.append(f"rubric={metrics['rubric_score']:.2f}")
        if "judge_score" in metrics:
            quality_parts.append(f"judge={metrics['judge_score']:.2f}")

        print(
            f"{result['name']:<28} {result['status']:<8} "
            f"score={metrics['final_score']:.4f} "
            f"{' '.join(quality_parts)} "
            f"p95={metrics['latency_p95']:.4f}s stdev={stdev:.4f}s",
            flush=True,
        )
    print("-" * 80, flush=True)
    print(f"QUALITY GATE: {quality_gate(results)}", flush=True)


if __name__ == "__main__":
    sys.exit(_main())

