import os

# Delegate file operations to canonical implementation in file_tools
from actions.tools.file_tools import (
    list_files as _file_list_files,
    read_file as _file_read_file,
    write_file as _file_write_file,
)


# =========================
# 📂 LIST FILES (delegated)
# =========================
def list_files(data=None, state=None):
    return _file_list_files(data, state)


def respond(data=None, state=None):
    if not isinstance(data, dict):
        data = {"output": str(data or "")}

    return {
        "status": data.get("status", "success"),
        "output": data.get("output", ""),
        "error": data.get("error"),
    }


# =========================
# 📄 READ FILE (delegated)
# =========================
def read_file(data, state=None):
    return _file_read_file(data, state)


# =========================
# ✍️ WRITE FILE (delegated)
# =========================
def write_file(data, state=None):
    return _file_write_file(data, state)
