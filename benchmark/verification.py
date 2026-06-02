import json
import os
import re
import subprocess
import sys
from pathlib import Path


DEFAULT_TIMEOUT_SECONDS = 10
MAX_CAPTURE_CHARS = 4000


class BenchmarkConfigurationError(ValueError):
    pass


def apply_setup(root, setup):
    """Create deterministic workspace fixtures for one benchmark run."""
    if not setup:
        return []

    root_path = _workspace_root(root)
    results = []

    for directory in _setup_dirs(setup):
        path = _resolve_workspace_path(root_path, directory)
        path.mkdir(parents=True, exist_ok=True)
        results.append(
            {
                "type": "dir",
                "path": _relative_workspace_path(root_path, path),
                "status": "success",
            }
        )

    for spec in _setup_files(setup):
        path = _resolve_workspace_path(root_path, spec.get("path"))
        path.parent.mkdir(parents=True, exist_ok=True)
        content = _setup_file_content(spec)
        path.write_text(content, encoding=str(spec.get("encoding") or "utf-8"))
        results.append(
            {
                "type": "file",
                "path": _relative_workspace_path(root_path, path),
                "status": "success",
                "bytes": len(content.encode(str(spec.get("encoding") or "utf-8"))),
            }
        )

    return results


def run_verifications(root, verification, sandbox=False):
    checks = _verification_checks(verification)
    if not checks:
        return []

    root_path = _workspace_root(root)
    results = []
    for index, check in enumerate(checks):
        results.append(_run_check(root_path, check, index, sandbox=sandbox))
    return results


def critical_verifications_passed(results):
    return all(
        bool(result.get("passed"))
        for result in results or []
        if bool(result.get("critical", True))
    )


def verification_summary(results):
    results = list(results or [])
    critical = [result for result in results if result.get("critical", True)]
    failed = [result for result in results if not result.get("passed")]
    critical_failed = [result for result in critical if not result.get("passed")]
    return {
        "total": len(results),
        "passed": len(results) - len(failed),
        "failed": len(failed),
        "critical_total": len(critical),
        "critical_failed": len(critical_failed),
        "ok": not critical_failed,
    }


def _run_check(root, check, index, sandbox=False):
    if not isinstance(check, dict):
        return _result(
            check_type="invalid",
            name=f"verification_{index}",
            critical=True,
            passed=False,
            error="verification_check_must_be_object",
        )

    check_type = str(check.get("type") or check.get("check") or "").strip()
    name = str(check.get("name") or check_type or f"verification_{index}")
    critical = bool(check.get("critical", True))

    try:
        handlers = {
            "file_exists": _check_file_exists,
            "file_equals": _check_file_equals,
            "file_contains": _check_file_contains,
            "json_equals": _check_json_equals,
            "python_file": _check_python_file,
            "python_module": _check_python_module,
            "pytest": _check_pytest,
        }
        handler = handlers.get(check_type)
        if handler is None:
            return _result(
                check_type=check_type or "missing",
                name=name,
                critical=critical,
                passed=False,
                error=f"unknown_verification_type:{check_type}",
            )

        details = handler(root, check, sandbox=sandbox)
        return _result(
            check_type=check_type,
            name=name,
            critical=critical,
            passed=bool(details.pop("passed")),
            **details,
        )
    except Exception as exc:
        return _result(
            check_type=check_type or "error",
            name=name,
            critical=critical,
            passed=False,
            error=str(exc),
        )


def _check_file_exists(root, check, sandbox=False):
    path = _resolve_workspace_path(root, check.get("path"))
    exists = path.exists()
    expected_kind = check.get("kind")
    if expected_kind == "file":
        exists = path.is_file()
    elif expected_kind == "dir":
        exists = path.is_dir()
    return {
        "passed": exists,
        "path": _relative_workspace_path(root, path),
    }


def _check_file_equals(root, check, sandbox=False):
    path = _resolve_workspace_path(root, check.get("path"))
    expected = str(check.get("content", check.get("equals", "")))
    actual = path.read_text(encoding=str(check.get("encoding") or "utf-8"))
    return {
        "passed": actual == expected,
        "path": _relative_workspace_path(root, path),
        "expected_size": len(expected),
        "actual_size": len(actual),
    }


def _check_file_contains(root, check, sandbox=False):
    path = _resolve_workspace_path(root, check.get("path"))
    actual = path.read_text(encoding=str(check.get("encoding") or "utf-8"))
    contains = check.get("contains", [])
    if isinstance(contains, str):
        contains = [contains]
    contains_any = check.get("contains_any", [])
    if isinstance(contains_any, str):
        contains_any = [contains_any]

    all_match = all(str(fragment) in actual for fragment in contains)
    any_match = True
    if contains_any:
        any_match = any(str(fragment) in actual for fragment in contains_any)

    return {
        "passed": all_match and any_match,
        "path": _relative_workspace_path(root, path),
        "actual_size": len(actual),
    }


def _check_json_equals(root, check, sandbox=False):
    path = _resolve_workspace_path(root, check.get("path"))
    actual = json.loads(path.read_text(encoding=str(check.get("encoding") or "utf-8")))
    expected = check.get("equals", check.get("json"))
    return {
        "passed": actual == expected,
        "path": _relative_workspace_path(root, path),
    }


def _check_python_file(root, check, sandbox=False):
    path = _resolve_workspace_path(root, check.get("path"))
    if not path.is_file():
        raise BenchmarkConfigurationError("python_file_not_found")
    args = _string_list(check.get("args", []), "args")
    command = [sys.executable, "-I", _relative_workspace_path(root, path), *args]
    return _run_command_check(root, command, check, sandbox=sandbox)


def _check_python_module(root, check, sandbox=False):
    module = str(check.get("module") or "")
    if not re.fullmatch(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*", module):
        raise BenchmarkConfigurationError("invalid_python_module")
    args = _string_list(check.get("args", []), "args")
    if sandbox:
        code = (
            "import runpy, sys; "
            "sys.path.insert(0, '.'); "
            f"runpy.run_module({module!r}, run_name='__main__')"
        )
        command = [sys.executable, "-I", "-c", code, *args]
    else:
        command = [sys.executable, "-m", module, *args]
    return _run_command_check(root, command, check, sandbox=sandbox)


def _check_pytest(root, check, sandbox=False):
    args = _string_list(check.get("args", ["-q"]), "args")
    paths = check.get("paths", check.get("path", []))
    if isinstance(paths, str):
        paths = [paths]
    if paths is None:
        paths = []
    if not isinstance(paths, list):
        raise BenchmarkConfigurationError("pytest_paths_must_be_list_or_string")

    safe_paths = []
    for path in paths:
        resolved = _resolve_workspace_path(root, path)
        safe_paths.append(_relative_workspace_path(root, resolved))

    command = [sys.executable, "-I", "-m", "pytest", *args, *safe_paths]
    return _run_command_check(root, command, check, sandbox=sandbox)


def _run_command_check(root, command, check, sandbox=False):
    timeout = _timeout(check)
    env = os.environ.copy()
    if sandbox:
        env = _prepare_sandbox_env(env)

    completed = subprocess.run(
        command,
        cwd=str(root),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    expected_returncode = int(check.get("returncode", 0))
    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    passed = completed.returncode == expected_returncode
    passed = passed and _text_expectations_pass(stdout, check, "stdout")
    passed = passed and _text_expectations_pass(stderr, check, "stderr")

    return {
        "passed": passed,
        "command": command,
        "returncode": completed.returncode,
        "expected_returncode": expected_returncode,
        "stdout": _truncate(stdout),
        "stderr": _truncate(stderr),
    }


def _text_expectations_pass(text, check, stream):
    equals_key = f"{stream}_equals"
    contains_key = f"{stream}_contains"
    any_key = f"{stream}_contains_any"

    if equals_key in check and text.strip() != str(check[equals_key]).strip():
        return False

    contains = check.get(contains_key, [])
    if isinstance(contains, str):
        contains = [contains]
    if any(str(fragment) not in text for fragment in contains):
        return False

    contains_any = check.get(any_key, [])
    if isinstance(contains_any, str):
        contains_any = [contains_any]
    if contains_any and not any(str(fragment) in text for fragment in contains_any):
        return False

    return True


def _setup_dirs(setup):
    dirs = setup.get("dirs", []) if isinstance(setup, dict) else []
    if isinstance(dirs, str):
        return [dirs]
    if not isinstance(dirs, list):
        raise BenchmarkConfigurationError("setup.dirs_must_be_list_or_string")

    normalized = []
    for item in dirs:
        if isinstance(item, dict):
            normalized.append(item.get("path"))
        else:
            normalized.append(item)
    return normalized


def _setup_files(setup):
    files = setup.get("files", []) if isinstance(setup, dict) else []
    if isinstance(files, dict):
        return [{"path": path, "content": content} for path, content in files.items()]
    if not isinstance(files, list):
        raise BenchmarkConfigurationError("setup.files_must_be_list_or_mapping")

    normalized = []
    for item in files:
        if not isinstance(item, dict):
            raise BenchmarkConfigurationError("setup.file_must_be_object")
        normalized.append(item)
    return normalized


def _setup_file_content(spec):
    if "json" in spec:
        return json.dumps(spec["json"], ensure_ascii=False, indent=2)
    return str(spec.get("content", ""))


def _verification_checks(verification):
    if not verification:
        return []
    if isinstance(verification, list):
        return verification
    if isinstance(verification, dict):
        if isinstance(verification.get("checks"), list):
            return verification["checks"]
        if verification.get("type") or verification.get("check"):
            return [verification]
    raise BenchmarkConfigurationError("verification_must_be_list_or_object")


def _workspace_root(root):
    return Path(root).resolve()


def _resolve_workspace_path(root, path):
    if not isinstance(path, str) or not path.strip():
        raise BenchmarkConfigurationError("path_missing")

    candidate = Path(path)
    if candidate.is_absolute():
        resolved = candidate.resolve()
    else:
        resolved = (root / candidate).resolve()

    root_str = str(root)
    resolved_str = str(resolved)
    try:
        if os.path.commonpath([root_str, resolved_str]) != root_str:
            raise BenchmarkConfigurationError("path_outside_workspace")
    except ValueError as exc:
        raise BenchmarkConfigurationError("path_outside_workspace") from exc

    return resolved


def _relative_workspace_path(root, path):
    try:
        return Path(path).resolve().relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _string_list(value, name):
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if not isinstance(value, list):
        raise BenchmarkConfigurationError(f"{name}_must_be_list_or_string")
    return [str(item) for item in value]


def _timeout(check):
    try:
        timeout = float(check.get("timeout", DEFAULT_TIMEOUT_SECONDS))
    except (TypeError, ValueError):
        timeout = DEFAULT_TIMEOUT_SECONDS
    return max(0.1, min(timeout, 60.0))


def _truncate(text):
    text = str(text or "")
    if len(text) <= MAX_CAPTURE_CHARS:
        return text
    return text[:MAX_CAPTURE_CHARS] + "\n...<truncated>"


def _prepare_sandbox_env(env):
    """Sanitize an environment mapping for sandboxed subprocess execution.

    This removes common secret/proxy-related variables and forces Python
    into isolated mode via `PYTHONNOUSERSITE` and clearing `PYTHONPATH`.
    """
    out = dict(env or {})
    # remove obvious secrets and proxies
    for key in list(out.keys()):
        k = key.upper()
        if (
            k.startswith("AWS")
            or k.startswith("GITHUB")
            or k.startswith("GH_")
            or k.startswith("OPENAI")
            or k.startswith("AZURE")
            or k.startswith("GOOGLE")
            or "TOKEN" in k
            or "SECRET" in k
            or "KEY" in k and not k == "PATH"
            or "PASSWORD" in k
            or "CREDENTIAL" in k
            or "PROXY" in k
            or "SSL" in k
            or "CERT" in k
        ):
            out.pop(key, None)

    out["PYTHONNOUSERSITE"] = "1"
    out["PYTHONPATH"] = ""
    return out


def _result(check_type, name, critical, passed, **details):
    result = {
        "name": name,
        "type": check_type,
        "critical": bool(critical),
        "passed": bool(passed),
    }
    result.update(details)
    return result
