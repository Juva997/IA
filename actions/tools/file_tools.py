import os
import re


def _safe_path(path, state=None):
    if not isinstance(path, str) or not path.strip():
        raise ValueError("path_missing")

    base_dir = _workspace_root(state)
    full_path = os.path.abspath(os.path.join(base_dir, path))

    if os.path.commonpath([base_dir, full_path]) != base_dir:
        raise ValueError("path_outside_safe_root")

    return full_path


def _workspace_root(state=None):
    if isinstance(state, dict):
        root = state.get("workspace_root")
        if not root and isinstance(state.get("metadata"), dict):
            root = state["metadata"].get("workspace_root")
        if root:
            return os.path.abspath(root)
    return os.path.abspath(os.getcwd())


def delete_file(data, state=None):
    try:
        path = data.get("path")

        if not path:
            return {"status": "error", "error": "path_missing"}

        safe = _safe_path(path, state)

        if not os.path.exists(safe):
            return {"status": "error", "error": "arquivo_nao_existe"}

        if not os.path.isfile(safe):
            return {"status": "error", "error": "not_a_file"}

        os.remove(safe)

        return {"status": "success", "output": f"removido: {path}"}

    except Exception as e:
        return {"status": "error", "error": str(e)}


def create_folder(data, state=None):
    try:
        path = data.get("path")

        if not path:
            return {"status": "error", "error": "path_missing"}

        safe = _safe_path(path, state)

        os.makedirs(safe, exist_ok=True)

        return {"status": "success", "output": f"pasta criada: {path}"}

    except Exception as e:
        return {"status": "error", "error": str(e)}


def write_file(data, state=None):
    try:
        path = data.get("path")
        content = data.get("content", "")

        if not path:
            return {"status": "error", "error": "path_missing"}

        safe = _safe_path(path, state)
        content = _sanitize_file_content(path, content)
        content = _normalize_code_content(content)
        content = _repair_python_source(content)

        # 🔥 evita erro quando não há diretório (ex: "teste.txt")
        directory = os.path.dirname(safe)
        if directory:
            os.makedirs(directory, exist_ok=True)

        with open(safe, "w", encoding="utf-8") as f:
            f.write(content)

        return {"status": "success", "output": f"arquivo criado: {path}"}

    except Exception as e:
        return {"status": "error", "error": str(e)}


def read_file(data, state=None):
    try:
        path = data.get("path")

        if not path:
            return {"status": "error", "error": "path_missing"}

        safe = _safe_path(path, state)

        if not os.path.exists(safe):
            return {"status": "error", "error": "arquivo_nao_existe"}

        if not os.path.isfile(safe):
            return {"status": "error", "error": "not_a_file"}

        with open(safe, "r", encoding="utf-8") as f:
            content = f.read().strip()

        # 🔥 DETECTAR E CALCULAR SOMA SE FOR NÚMEROS SEPARADOS POR VÍRGULA
        if ',' in content and all(part.strip().isdigit() for part in content.split(',')):
            try:
                numbers = [int(x.strip()) for x in content.split(',')]
                total = sum(numbers)
                return {"status": "success", "output": f"{content}\n\nSoma dos números: {total}"}
            except ValueError:
                pass  # Se não conseguir converter, continua normal

        return {"status": "success", "output": content}

    except Exception as e:
        return {"status": "error", "error": str(e)}


def _sanitize_file_content(path, content):
    if not isinstance(content, str):
        return content

    pattern = rf"exec\(\s*open\(['\"]{re.escape(path)}['\"]\)\.read\(\)\s*\)"
    if re.search(pattern, content):
        content = re.sub(
            pattern,
            "# self-exec removed to prevent recursive execution",
            content,
        )
    return content


def _normalize_code_content(content):
    if not isinstance(content, str):
        return content

    content = re.sub(r"__name__\s*==\s*['\"]__main__0['\"]", "__name__ == '__main__'", content)
    content = re.sub(r"__name__\s*==\s*['\"]__main__\s*['\"]", "__name__ == '__main__'", content)
    content = "".join(ch for ch in content if ch.isprintable() or ch in "\n\r\t")
    return content


def _repair_python_source(content):
    if not isinstance(content, str):
        return content

    content = re.sub(r"(class [^(]+\(.*?\):)\s+def ", r"\1\n    def ", content)
    content = re.sub(r"\)\s+def ", r")\n    def ", content)
    content = re.sub(r": {8,}", ":\n        ", content)
    content = re.sub(r" {8,}", "\n        ", content)
    content = re.sub(r"\nif __name__ == '__main__':\s+", r"\nif __name__ == '__main__':\n    ", content)
    return content


