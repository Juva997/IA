import os

# =========================
# 🔒 PATH SAFETY
# =========================
def _safe_path(path, state=None):
    if not path:
        raise Exception("path_missing")

    base_dir = _workspace_root(state)
    full = os.path.abspath(os.path.join(base_dir, path))

    if os.path.commonpath([os.path.abspath(base_dir), full]) != os.path.abspath(base_dir):
        raise Exception("acesso fora do diretório permitido")

    return full


def _workspace_root(state=None):
    if isinstance(state, dict):
        root = state.get("workspace_root")
        if not root and isinstance(state.get("metadata"), dict):
            root = state["metadata"].get("workspace_root")
        if root:
            return os.path.abspath(root)
    return os.path.abspath(os.getcwd())


# =========================
# 📂 LIST FILES
# =========================
def list_files(data=None, state=None):
    try:
        path = _get_path(data, default=".")
        safe = _safe_path(path, state)

        files = os.listdir(safe)
        # Format as readable list for better output
        formatted_list = "\n".join([f"  - {f}" for f in sorted(files)])
        output = f"Arquivos na pasta '{path}':\n{formatted_list}"
        
        return {"status": "success", "output": output}

    except Exception as e:
        return _error(str(e))


def respond(data=None, state=None):
    if not isinstance(data, dict):
        data = {"output": str(data or "")}

    return {
        "status": data.get("status", "success"),
        "output": data.get("output", ""),
        "error": data.get("error"),
    }


# =========================
# 📄 READ FILE
# =========================
def read_file(data, state=None):
    try:
        path = _get_path(data)
        safe = _safe_path(path, state)

        with open(safe, "r", encoding="utf-8") as f:
            content = f.read().strip()

        if ',' in content and all(part.strip().isdigit() for part in content.split(',')):
            try:
                numbers = [int(x.strip()) for x in content.split(',')]
                return {"status": "success", "output": f"{content}\n\nSoma dos numeros: {sum(numbers)}"}
            except ValueError:
                pass

        return {"status": "success", "output": content}

    except Exception as e:
        return _error(str(e))


# =========================
# ✍️ WRITE FILE
# =========================
def write_file(data, state=None):
    try:
        path = _get_path(data)
        content = _get_content(data)

        safe = _safe_path(path, state)

        with open(safe, "w", encoding="utf-8") as f:
            f.write(content)

        return {"status": "success", "output": f"salvo: {safe}"}

    except Exception as e:
        return _error(str(e))


# =========================
# 🔍 HELPERS
# =========================
def _get_path(data, default=None):
    if not isinstance(data, dict):
        return default
    return data.get("path", default)


def _get_content(data):
    if not isinstance(data, dict):
        return ""
    return data.get("content", "")


def _error(msg):
    return {"status": "error", "output": None, "error": msg}
