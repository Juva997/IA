import traceback
import os
import subprocess
import shutil
import tempfile
from monitor.logger import Logger


class Executor:
    def __init__(self, registry, max_retries=2):
        self.registry = registry
        self.max_retries = max_retries
        self.logger = Logger()

    # =========================
    def execute(self, decision, state):
        if not self._is_valid_decision(decision):
            return self._error("invalid_decision_format")

        action = decision.get("action")
        action_type = decision.get("type", "tool")
        data = self._sanitize_data(action, decision.get("data"))

        if data is None:
            return self._error("invalid_data_after_sanitize")

        if action_type == "specialist":
            return self._execute_specialist(action, state)

        # fluxo especial: aplicar patch gerado por LLM com backup + pytest + rollback
        if action in ("apply_llm_patches", "apply_patch", "apply_patch_with_tests"):
            return self._apply_patch_flow(data, state)

        tool = self.registry.get(action)
        if not tool:
            return self._error(f"tool_not_found: {action}")

        return self._safe_execute(tool, data, state, action)

    # =========================
    def _is_valid_decision(self, decision):
        return isinstance(decision, dict) and decision.get("action")

    # =========================
    def _sanitize_data(self, action, data):
        if data is None:
            return {}

        if isinstance(data, str):
            return self._sanitize_string_input(action, data)

        if isinstance(data, dict):
            return self._normalize_data_fields(action, data)

        return {"input": str(data)}

    # =========================
    def _normalize_data_fields(self, action, data):
        if not isinstance(data, dict):
            return data

        if action == "write_file":
            if "path" not in data:
                if "file_path" in data:
                    data["path"] = data.pop("file_path")
                elif "filename" in data:
                    data["path"] = data.pop("filename")
                elif "file" in data:
                    data["path"] = data.pop("file")
            # Converter lista para string se necessário
            if isinstance(data.get("path"), list) and data["path"]:
                data["path"] = (
                    data["path"][0]
                    if len(data["path"]) == 1
                    else "/".join(map(str, data["path"]))
                )

        if action == "run_python":
            if "code" not in data and "file_path" in data:
                file_path = data.get("file_path")
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data["code"] = f.read()
                except Exception:
                    pass

        if action in ["create_folder", "delete_file", "read_file"]:
            if "path" not in data:
                if "folder" in data:
                    data["path"] = data.pop("folder")
                elif "directory" in data:
                    data["path"] = data.pop("directory")
            # Converter lista para string se necessário
            if isinstance(data.get("path"), list) and data["path"]:
                data["path"] = (
                    data["path"][0]
                    if len(data["path"]) == 1
                    else "/".join(map(str, data["path"]))
                )

        return data

    # =========================
    def _sanitize_string_input(self, action, data):
        data = data.strip()

        if action == "write_file":
            if "|" not in data:
                return None
            path, content = data.split("|", 1)
            return {"path": path.strip(), "content": content}

        if action in ["create_folder", "delete_file"]:
            return {"path": data}

        if action == "run_python":
            return {"code": data}

        return {"input": data}

    # =========================
    def _execute_specialist(self, action, state):
        try:
            return self._success(f"specialist_executed: {action}")
        except Exception as e:
            return self._error(f"specialist_error: {str(e)}")

    # =========================
    def _apply_patch_flow(self, data, state):
        try:
            # import dinamico para evitar import circular
            from benchmark.repair import apply_llm_patches, rollback_patches
        except Exception as e:
            return self._error(f"import_error: {str(e)}")

        # extrair texto do patch
        text = None
        if isinstance(data, str):
            text = data
        elif isinstance(data, dict):
            text = data.get("text") or data.get("patch") or data.get("content") or data.get("llm_output")
        else:
            return self._error("invalid_patch_data")

        if not text:
            return self._error("patch_text_missing")

        # determinar workspace root
        root = None
        if isinstance(state, dict):
            root = state.get("workspace_root") or (state.get("metadata") or {}).get("workspace_root")
        if not root:
            root = os.path.abspath(os.getcwd())

        # Aplicar patches em uma cópia temporária do workspace e executar
        # os testes nessa cópia. Só publicar as mudanças no workspace real
        # se os testes passarem.
        run_tests = True
        timeout = 120
        if isinstance(data, dict):
            if "run_tests" in data:
                run_tests = bool(data.get("run_tests"))
            if "timeout" in data:
                try:
                    timeout = int(data.get("timeout"))
                except Exception:
                    pass

        # criar cópia temporária do workspace
        tmp_root = None
        try:
            tmp_root = tempfile.mkdtemp(prefix="assistente_patch_")
            shutil.copytree(root, tmp_root, dirs_exist_ok=True)
        except Exception as e:
            try:
                if tmp_root and os.path.exists(tmp_root):
                    shutil.rmtree(tmp_root)
            except Exception:
                pass
            return self._error(f"workspace_copy_error: {str(e)}")

        try:
            applied, errors, _ = apply_llm_patches(tmp_root, text)
        except Exception as e:
            try:
                if tmp_root and os.path.exists(tmp_root):
                    shutil.rmtree(tmp_root)
            except Exception:
                pass
            return self._error(f"apply_error: {str(e)}")

        if errors:
            try:
                if tmp_root and os.path.exists(tmp_root):
                    shutil.rmtree(tmp_root)
            except Exception:
                pass
            return {"status": "error", "output": None, "error": "apply_errors", "details": errors}

        # rodar pytest na cópia temporária quando solicitado
        if run_tests:
            try:
                proc = subprocess.run(["pytest", "-q"], capture_output=True, text=True, timeout=timeout, cwd=tmp_root)
            except Exception as e:
                try:
                    if tmp_root and os.path.exists(tmp_root):
                        shutil.rmtree(tmp_root)
                except Exception:
                    pass
                return {"status": "error", "output": None, "error": f"pytest_error: {str(e)}", "applied": applied}

            if proc.returncode != 0:
                try:
                    if tmp_root and os.path.exists(tmp_root):
                        shutil.rmtree(tmp_root)
                except Exception:
                    pass
                return {
                    "status": "error",
                    "error": "tests_failed",
                    "output": (proc.stdout or "") + "\n" + (proc.stderr or ""),
                    "applied": applied,
                }

        # Publicar as alterações no workspace real (com backup)
        final_backups = []

        # SECURITY: publishing patches to the real workspace is disabled by default.
        # To enable in non-production/testing environments set ASSISTENTE_PUBLISH_PATCHES=1
        publish_allowed = os.environ.get("ASSISTENTE_PUBLISH_PATCHES", "0").strip().lower() in ("1", "true", "yes")
        if not publish_allowed:
            try:
                if tmp_root and os.path.exists(tmp_root):
                    shutil.rmtree(tmp_root)
            except Exception:
                pass
            return {"status": "error", "error": "publish_disabled_env", "applied": applied}

        # Additional safeguards before publishing:
        # - limit number of files changed
        # - block changes to critical paths unless a SecurityManager allows it
        # - block publishing when on `main`/`master` branch unless explicitly allowed
        max_files = int(os.environ.get("ASSISTENTE_PUBLISH_MAX_FILES", "20"))
        blocked_paths = [
            "core",
            "security",
            "memory",
            "bootstrap",
            "actions",
            "monitor",
            "integrations",
            ".github",
            "Dockerfile",
            "docker-compose.yml",
            "pyproject.toml",
            "requirements.txt",
            "requirements-ci.txt",
        ]

        try:
            # quick size check
            if len(applied) > max_files:
                try:
                    if tmp_root and os.path.exists(tmp_root):
                        shutil.rmtree(tmp_root)
                except Exception:
                    pass
                return {"status": "error", "error": "publish_too_many_files", "applied": applied}

            # If repo is git, avoid publishing directly to main/master by default
            if os.path.isdir(os.path.join(root, ".git")):
                try:
                    br = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=root, capture_output=True, text=True, timeout=5)
                    branch = (br.stdout or "").strip()
                    if branch in ("main", "master") and os.environ.get("ASSISTENTE_PUBLISH_ON_MAIN", "0").strip().lower() not in ("1", "true", "yes"):
                        try:
                            if tmp_root and os.path.exists(tmp_root):
                                shutil.rmtree(tmp_root)
                        except Exception:
                            pass
                        return {"status": "error", "error": "publish_on_main_blocked", "branch": branch}
                except Exception:
                    # if git check fails, be conservative and continue
                    pass

            # Try to use SecurityManager if available to validate writes
            sec = None
            try:
                from security.security import SecurityManager

                sec = SecurityManager(safe_root=root)
            except Exception:
                sec = None

            # Validate each file change against security policy / blocked paths
            for entry in applied:
                rel = entry.get("path")
                if not rel:
                    continue
                normalized = rel.replace("\\", "/").lstrip("/")
                # Reject obvious modifications to blocked paths when no SecurityManager
                if sec is None:
                    for bp in blocked_paths:
                        if normalized == bp or normalized.startswith(bp.rstrip("/") + "/"):
                            try:
                                if tmp_root and os.path.exists(tmp_root):
                                    shutil.rmtree(tmp_root)
                            except Exception:
                                pass
                            return {"status": "error", "error": f"blocked_path:{rel}", "applied": applied}

            # All pre-checks passed; now apply changes but validate per-file via SecurityManager if available
            try:
                for entry in applied:
                    rel = entry.get("path")
                    if not rel:
                        continue
                    src = os.path.join(tmp_root, rel)
                    dst = os.path.join(root, rel)
                    existed = os.path.exists(dst)
                    original = ""
                    if existed:
                        try:
                            with open(dst, "r", encoding="utf-8") as f:
                                original = f.read()
                        except Exception:
                            original = None
                    final_backups.append({"path": rel, "original": original, "existed": existed})

                    # garantir diretório
                    dstdir = os.path.dirname(dst)
                    if dstdir:
                        os.makedirs(dstdir, exist_ok=True)

                    # se arquivo novo/alterado, copiar do tmp para o destino
                    if os.path.exists(src) and os.path.isfile(src):
                        with open(src, "r", encoding="utf-8") as f:
                            new_content = f.read()

                        # Validate with SecurityManager if available
                        if sec is not None:
                            try:
                                ok = sec.validate_write(rel, new_content)
                                if not ok:
                                    raise PermissionError(f"security_manager_blocked:{rel}")
                            except Exception as secexc:
                                raise secexc

                        with open(dst, "w", encoding="utf-8") as f:
                            f.write(new_content)
                    else:
                        # se patch removeu o arquivo
                        if existed and os.path.exists(dst):
                            # for deletions, consult SecurityManager when available
                            if sec is not None:
                                allowed, reason = (True, None)
                                try:
                                    res = sec.validate_action({"action": "delete_file", "data": {"path": rel, "confirm_delete": True}})
                                    if isinstance(res, tuple) and len(res) >= 1:
                                        allowed = bool(res[0])
                                        reason = res[1] if len(res) > 1 else None
                                except Exception:
                                    allowed = False
                                if not allowed:
                                    raise PermissionError(f"security_manager_blocked_delete:{rel}:{reason}")

                            os.remove(dst)

            except Exception as e:
                # tentar rollback local usando backups
                for b in final_backups:
                    rel = b.get("path")
                    dst = os.path.join(root, rel)
                    try:
                        if b.get("existed"):
                            with open(dst, "w", encoding="utf-8") as f:
                                f.write(b.get("original") or "")
                        elif os.path.exists(dst):
                            os.remove(dst)
                    except Exception:
                        pass
                try:
                    if tmp_root and os.path.exists(tmp_root):
                        shutil.rmtree(tmp_root)
                except Exception:
                    pass
                return {"status": "error", "error": f"apply_publish_error:{str(e)}", "applied": applied}

        except Exception as e:
            try:
                if tmp_root and os.path.exists(tmp_root):
                    shutil.rmtree(tmp_root)
            except Exception:
                pass
            return {"status": "error", "error": f"apply_publish_precheck_error:{str(e)}", "applied": applied}

        # cleanup temporário
        try:
            if tmp_root and os.path.exists(tmp_root):
                shutil.rmtree(tmp_root)
        except Exception:
            pass

        return {"status": "success", "output": f"applied {len(applied)} patches", "patches": applied}

    # =========================
    def _safe_execute(self, tool, data, state, action=None):
        attempts = 0

        # Lazy import of tracing/metrics helpers (optional)
        tracer = None
        metrics = None
        try:
            from integrations.otel import get_tracer, get_metrics

            tracer = get_tracer("executor")
            metrics = get_metrics()
        except Exception:
            tracer = None
            metrics = None

        while attempts <= self.max_retries:
            try:
                # If configured, offload run_python to the queue (PoC using RQ)
                try:
                    if (action or "").lower() == "run_python":
                        from integrations.queue_client import enqueue_run_python

                        job = enqueue_run_python(data, state)
                        if job is not None:
                            # job enqueued -> return queued status
                            if metrics:
                                try:
                                    metrics.increment_requests("run_python_queued")
                                except Exception:
                                    pass
                            return self._normalize_result({"status": "queued", "output": None, "error": None, "job_id": job.get_id()})
                except Exception:
                    # Fail silently to fallback to local execution
                    pass

                # Instrument execution with tracing and timing
                start = None
                if tracer:
                    span = tracer.start_as_current_span("executor.tool_call", attributes={"action": action or ""})
                    span.__enter__()
                    start = None
                try:
                    import time

                    start = time.perf_counter()
                    result = tool(data, state)
                    duration = time.perf_counter() - start
                finally:
                    if tracer:
                        try:
                            span.__exit__(None, None, None)
                        except Exception:
                            pass

                if metrics:
                    try:
                        metrics.increment_requests(action or "tool")
                        if hasattr(metrics, "observe_response_time") and start is not None:
                            metrics.observe_response_time(action or "tool", duration)
                    except Exception:
                        pass

                if isinstance(result, dict) and result.get("status") == "error":
                    error_message = result.get("error") or result.get("output")
                    try:
                        self.logger.error(f"[TOOL ERROR] {error_message}")
                    except Exception:
                        # fallback to print if logger fails
                        print(f"[TOOL ERROR] {error_message}")

                return self._normalize_result(result)

            except Exception as e:
                attempts += 1
                _tb = traceback.format_exc()

                if attempts > self.max_retries:
                    return self._error(f"execution_failed: {str(e)}")

    # =========================
    def _normalize_result(self, result):
        if isinstance(result, dict):
            normalized = {
                "status": result.get("status") or ("error" if result.get("error") else "success"),
                "output": result.get("output"),
                "error": result.get("error"),
            }

            for key, value in result.items():
                if key not in normalized:
                    normalized[key] = value

            if normalized["status"] == "success" and normalized["output"] is None:
                normalized["output"] = ""

            if normalized["status"] == "error" and normalized["error"] is None:
                normalized["error"] = str(normalized.get("output") or "unknown_error")

            return normalized

        return {"status": "success", "output": result, "error": None}

    # =========================
    def _error(self, message):
        return {"status": "error", "output": None, "error": message}

    def _success(self, message):
        return {"status": "success", "output": message, "error": None}
