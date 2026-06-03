import ast
import builtins
import io
import json
import multiprocessing
import os
import sys
import tempfile
import uuid


FORBIDDEN_TOKENS = [
    "os.system",
    "os.popen",
    "os.exec",
    "subprocess",
    "__import__",
    "importlib",
    "eval(",
    "compile(",
    "#!/",
    "source ",
    "bash",
    "sh ",
]

SAFE_MODULES = {
    "collections",
    "csv",
    "datetime",
    "decimal",
    "fractions",
    "functools",
    "itertools",
    "json",
    "math",
    "random",
    "re",
    "statistics",
    "time",
    "unittest",
}

SAFE_BUILTINS = {
    "ArithmeticError": ArithmeticError,
    "AssertionError": AssertionError,
    "Exception": Exception,
    "False": False,
    "IndexError": IndexError,
    "KeyError": KeyError,
    "None": None,
    "RuntimeError": RuntimeError,
    "True": True,
    "TypeError": TypeError,
    "ValueError": ValueError,
    "__build_class__": __build_class__,
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "chr": chr,
    "dict": dict,
    "enumerate": enumerate,
    "filter": filter,
    "float": float,
    "int": int,
    "isinstance": isinstance,
    "issubclass": issubclass,
    "len": len,
    "list": list,
    "map": map,
    "max": max,
    "min": min,
    "object": object,
    "ord": ord,
    "pow": pow,
    "print": print,
    "range": range,
    "repr": repr,
    "reversed": reversed,
    "round": round,
    "set": set,
    "slice": slice,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "super": super,
    "tuple": tuple,
    "zip": zip,
}

FAST_PATH_MAX_SOURCE_BYTES = 4096


class SandboxValidationError(ValueError):
    pass


class SandboxValidator(ast.NodeVisitor):
    BLOCKED_CALLS = {
        "breakpoint",
        "compile",
        "delattr",
        "dir",
        "eval",
        "getattr",
        "globals",
        "help",
        "input",
        "locals",
        "setattr",
        "vars",
    }
    BLOCKED_ATTRS = {
        "chmod",
        "chown",
        "execv",
        "execve",
        "fork",
        "kill",
        "modules",
        "popen",
        "remove",
        "rename",
        "replace",
        "rmdir",
        "spawn",
        "system",
        "unlink",
        "walk",
    }
    ALLOWED_DUNDER_NAMES = {"__name__"}

    def visit_Import(self, node):
        for alias in node.names:
            self._validate_module(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.level:
            raise SandboxValidationError("relative_import_blocked")
        self._validate_module(node.module or "")
        self.generic_visit(node)

    def visit_Name(self, node):
        if node.id == "exec":
            raise SandboxValidationError("exec_alias_blocked")
        if node.id.startswith("__") and node.id not in self.ALLOWED_DUNDER_NAMES:
            raise SandboxValidationError(f"dunder_name_blocked:{node.id}")
        self.generic_visit(node)

    def visit_Attribute(self, node):
        if node.attr.startswith("__") or node.attr in self.BLOCKED_ATTRS:
            raise SandboxValidationError(f"attribute_blocked:{node.attr}")
        self.generic_visit(node)

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name):
            name = node.func.id
            if name in self.BLOCKED_CALLS:
                raise SandboxValidationError(f"call_blocked:{name}")
            if name == "exec" and not self._is_allowed_exec(node):
                raise SandboxValidationError("exec_only_allowed_for_safe_file_read")
            if name == "exec":
                for arg in node.args:
                    self.visit(arg)
                return
        self.generic_visit(node)

    def _validate_module(self, name):
        root = name.split(".", 1)[0]
        if root not in SAFE_MODULES:
            raise SandboxValidationError(f"import_blocked:{root}")

    def _is_allowed_exec(self, node):
        if len(node.args) != 1 or node.keywords:
            return False

        arg = node.args[0]
        if not isinstance(arg, ast.Call):
            return False
        if not isinstance(arg.func, ast.Attribute) or arg.func.attr != "read":
            return False
        if arg.args or arg.keywords:
            return False

        open_call = arg.func.value
        if not isinstance(open_call, ast.Call):
            return False
        if not isinstance(open_call.func, ast.Name) or open_call.func.id != "open":
            return False
        if not open_call.args:
            return False

        file_arg = open_call.args[0]
        return isinstance(file_arg, ast.Constant) and isinstance(file_arg.value, str)


def run_python_code(data, state=None):
    code = _extract_code(data)

    if not isinstance(code, str):
        return _error("code must be string")

    if _contains_forbidden(code):
        return _error("codigo bloqueado por seguranca")

    code = _normalize_code_text(code)
    code = _repair_python_source(code)

    validation_error = _validate_code(code)
    if validation_error:
        return _error(validation_error)

    timeout_seconds = _extract_timeout(data)
    sandbox_root = _sandbox_root(state)

    fast_result = _run_fast_if_simple(code, sandbox_root)
    if fast_result is not None:
        return fast_result

    return _run_in_subprocess(code, sandbox_root, timeout_seconds)


def _run_fast_if_simple(code, sandbox_root):
    fast_source = _fast_path_source(code, sandbox_root)
    if fast_source is None:
        return None
    return _execute_in_sandbox(fast_source, sandbox_root)


def _run_in_subprocess(code, sandbox_root, timeout_seconds):
    os.makedirs(sandbox_root, exist_ok=True)
    ctx = multiprocessing.get_context("spawn")
    result_path = os.path.join(
        sandbox_root,
        f".sandbox_result_{os.getpid()}_{uuid.uuid4().hex}.json",
    )
    process = ctx.Process(target=_worker_execute, args=(code, sandbox_root, result_path))
    process.daemon = True
    process.start()
    process.join(timeout_seconds)

    if process.is_alive():
        process.terminate()
        process.join(1)
        _remove_result_file(result_path)
        return _error(f"timeout after {timeout_seconds}s")

    result = _read_result_file(result_path)
    _remove_result_file(result_path)

    if result is not None:
        return result

    if process.exitcode not in (0, None):
        return _error(f"sandbox_process_failed:{process.exitcode}")

    return {"status": "success", "output": "", "error": None}


def _worker_execute(code, sandbox_root, result_path):
    result = _execute_in_sandbox(code, sandbox_root)
    _write_result_file(result_path, result)


def _execute_in_sandbox(code, sandbox_root):
    old_stdout = sys.stdout
    old_cwd = os.getcwd()
    output = io.StringIO()

    try:
        os.makedirs(sandbox_root, exist_ok=True)
        os.chdir(sandbox_root)
        sys.stdout = output

        safe_builtins = dict(SAFE_BUILTINS)
        safe_builtins["open"] = _make_safe_open(sandbox_root)
        safe_builtins["__import__"] = _safe_import

        sandbox = {"__builtins__": safe_builtins, "__name__": "__main__"}
        safe_builtins["exec"] = _make_safe_exec(sandbox)
        exec(code, sandbox, sandbox)
        return {"status": "success", "output": output.getvalue().strip(), "error": None}

    except SystemExit as exc:
        if exc.code in (0, None, False):
            return {"status": "success", "output": output.getvalue().strip(), "error": None}
        return {"status": "error", "output": output.getvalue().strip(), "error": f"system_exit:{exc.code}"}
    except BaseException as exc:
        return {"status": "error", "output": output.getvalue().strip(), "error": str(exc)}
    finally:
        sys.stdout = old_stdout
        try:
            os.chdir(old_cwd)
        except Exception:
            pass


def _write_result_file(path, result):
    with builtins.open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False)


def _read_result_file(path):
    if not os.path.exists(path):
        return None

    try:
        with builtins.open(path, "r", encoding="utf-8") as f:
            result = json.load(f)
        return result if isinstance(result, dict) else None
    except Exception:
        return None


def _remove_result_file(path):
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


def _safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    root = name.split(".", 1)[0]
    if root not in SAFE_MODULES:
        raise ImportError(f"Import not allowed: {name}")
    return builtins.__import__(name, globals, locals, fromlist, level)


def _make_safe_exec(sandbox):
    def safe_exec(source, globals=None, locals=None):
        if not isinstance(source, str):
            raise PermissionError("exec accepts only source strings")

        source = _normalize_code_text(source)
        source = _repair_python_source(source)

        if _contains_forbidden(source):
            raise PermissionError("nested code blocked by security")

        validation_error = _validate_code(source)
        if validation_error:
            raise PermissionError(validation_error)

        return builtins.exec(source, sandbox, sandbox)

    return safe_exec


def _make_safe_open(root):
    root = os.path.abspath(root)

    def safe_open(file, mode="r", *args, **kwargs):
        if not isinstance(file, (str, bytes, os.PathLike)):
            raise PermissionError("invalid file path")

            # Negar modos que permitem escrita/atualização. Apenas leitura é permitida.
            if any(ch in mode for ch in ("w", "a", "x", "+")):
                raise PermissionError("write modes not allowed")

        full_path = os.path.abspath(os.path.join(root, os.fspath(file)))
        if os.path.commonpath([root, full_path]) != root:
            raise PermissionError("path outside sandbox")

        return builtins.open(full_path, mode, *args, **kwargs)

    return safe_open


def _fast_path_source(code, sandbox_root):
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None

    if _is_fast_module(tree, sandbox_root, depth=0):
        return code

    source = _fast_exec_source(tree, sandbox_root)
    if source is None:
        return None

    source = _repair_python_source(_normalize_code_text(source))
    if _validate_code(source):
        return None

    try:
        nested_tree = ast.parse(source)
    except SyntaxError:
        return None

    if _is_fast_module(nested_tree, sandbox_root, depth=1):
        return source

    return None


def _is_fast_path_safe(code, sandbox_root):
    return _fast_path_source(code, sandbox_root) is not None


def _fast_exec_source(tree, sandbox_root):
    body = getattr(tree, "body", None)
    if not isinstance(body, list) or len(body) != 1:
        return None

    stmt = body[0]
    if not isinstance(stmt, ast.Expr):
        return None

    expr = stmt.value
    if not isinstance(expr, ast.Call) or not _is_name_call(expr, "exec"):
        return None

    return _read_fast_exec_source(expr, sandbox_root)


def _is_fast_module(tree, sandbox_root, depth):
    body = getattr(tree, "body", None)
    if not isinstance(body, list) or not body or len(body) > 5:
        return False

    return all(_is_fast_statement(stmt, sandbox_root, depth) for stmt in body)


def _is_fast_statement(stmt, sandbox_root, depth):
    if not isinstance(stmt, ast.Expr):
        return False
    return _is_fast_expression(stmt.value, sandbox_root, depth)


def _is_fast_expression(expr, sandbox_root, depth):
    if not isinstance(expr, ast.Call):
        return False

    if _is_name_call(expr, "print"):
        return _is_fast_print_call(expr)

    return False


def _is_fast_print_call(call):
    if len(call.args) > 8:
        return False

    if not all(_is_fast_literal(arg) for arg in call.args):
        return False

    allowed_keywords = {"sep", "end", "flush"}
    for keyword in call.keywords:
        if keyword.arg not in allowed_keywords:
            return False
        if not _is_fast_literal(keyword.value):
            return False

    return True


def _is_fast_literal(node):
    if isinstance(node, ast.Constant):
        return True

    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        return isinstance(node.operand, ast.Constant) and isinstance(node.operand.value, (int, float, complex))

    if isinstance(node, ast.JoinedStr):
        return all(isinstance(value, ast.Constant) for value in node.values)

    return False


def _read_fast_exec_source(call, sandbox_root):
    path = _extract_exec_file_path(call)
    if not path:
        return None

    root = os.path.abspath(sandbox_root)
    full_path = os.path.abspath(os.path.join(root, path))

    try:
        if os.path.commonpath([root, full_path]) != root:
            return None
    except (OSError, ValueError):
        return None

    if not os.path.isfile(full_path):
        return None

    if os.path.getsize(full_path) > FAST_PATH_MAX_SOURCE_BYTES:
        return None

    try:
        with builtins.open(full_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return None


def _extract_exec_file_path(call):
    if len(call.args) != 1 or call.keywords:
        return None

    arg = call.args[0]
    if not isinstance(arg, ast.Call):
        return None
    if not isinstance(arg.func, ast.Attribute) or arg.func.attr != "read":
        return None
    if arg.args or arg.keywords:
        return None

    open_call = arg.func.value
    if not isinstance(open_call, ast.Call) or not _is_name_call(open_call, "open"):
        return None
    if len(open_call.args) != 1 or open_call.keywords:
        return None

    file_arg = open_call.args[0]
    if not isinstance(file_arg, ast.Constant) or not isinstance(file_arg.value, str):
        return None

    return file_arg.value


def _is_name_call(call, name):
    return isinstance(call.func, ast.Name) and call.func.id == name


def _extract_code(data):
    if isinstance(data, dict):
        return data.get("code", "")
    return data


def _extract_timeout(data):
    if not isinstance(data, dict):
        return 5

    try:
        timeout = int(data.get("timeout", 5))
    except (TypeError, ValueError):
        return 5

    return max(1, min(timeout, 10))


def _sandbox_root(state):
    if isinstance(state, dict) and state.get("sandbox_root"):
        root = state["sandbox_root"]
    elif (
        isinstance(state, dict)
        and isinstance(state.get("metadata"), dict)
        and state["metadata"].get("sandbox_root")
    ):
        root = state["metadata"]["sandbox_root"]
    else:
        root = os.path.join(tempfile.gettempdir(), "assistente_local_sandbox")

    return os.path.abspath(root)


def _contains_forbidden(code):
    if not isinstance(code, str):
        return False

    if code.startswith("#!"):
        code = "\n".join(code.splitlines()[1:])

    lowered = code.lower()
    return any(token.lower() in lowered for token in FORBIDDEN_TOKENS)


def _validate_code(code):
    try:
        tree = ast.parse(code)
        SandboxValidator().visit(tree)
    except SyntaxError as exc:
        return f"syntax_error:{exc.msg}"
    except SandboxValidationError as exc:
        return str(exc)
    return None


def _normalize_code_text(code):
    if not isinstance(code, str):
        return code

    code = re_sub(r"__name__\s*==\s*['\"]__main__0['\"]", "__name__ == '__main__'", code)
    code = re_sub(r"__name__\s*==\s*['\"]__main__\s*['\"]", "__name__ == '__main__'", code)
    return "".join(ch for ch in code if ch.isprintable() or ch in "\n\r\t")


def _repair_python_source(code):
    if not isinstance(code, str):
        return code

    code = re_sub(r"(class [^(]+\(.*?\):)\s+def ", r"\1\n    def ", code)
    code = re_sub(r"\)\s+def ", r")\n    def ", code)
    code = re_sub(r": {8,}", ":\n        ", code)
    code = re_sub(r" {8,}", "\n        ", code)
    code = re_sub(r"\nif __name__ == '__main__':\s+", r"\nif __name__ == '__main__':\n    ", code)
    return code


def re_sub(pattern, repl, text):
    import re

    return re.sub(pattern, repl, text)


def _error(msg):
    return {"status": "error", "output": None, "error": msg}
