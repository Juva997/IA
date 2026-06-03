#!/usr/bin/env python3
"""
scripts/remove_memory_entries.py
Safely remove episodes/lessons/skills or vector entries referencing a given substring
from the memory learning file (`data/vectors/memory.learning.json`).
Creates a backup before writing.

Usage:
    python scripts/remove_memory_entries.py "Leia-me.txt"

This script does NOT run automatically; revise the patterns if needed.
"""

import json
import sys
import os
import shutil


def main():
    if len(sys.argv) < 2:
        print("Uso: python scripts/remove_memory_entries.py <substring>")
        sys.exit(1)

    needle = sys.argv[1]
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    mem_path = os.path.join(repo_root, "data", "vectors", "memory.learning.json")

    if not os.path.exists(mem_path):
        print("Arquivo de memória não encontrado:", mem_path)
        sys.exit(1)

    # Load JSON (attempt to be permissive)
    with open(mem_path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except Exception as e:
            print("Falha ao ler JSON:", e)
            sys.exit(1)

    modified = False

    # Case 1: top-level dict with episodes/lessons/skills
    if isinstance(data, dict):
        for key in ("episodes", "lessons", "skills"):
            if key not in data:
                continue
            before = len(data[key]) if data[key] else 0
            if isinstance(data[key], list):
                data[key] = [item for item in data[key] if needle not in json.dumps(item, ensure_ascii=False)]
                after = len(data[key])
                if after != before:
                    print(f"Removidas {before-after} entradas em: {key}")
                    modified = True
            elif isinstance(data[key], dict):
                newd = {}
                for k, v in data[key].items():
                    if needle in json.dumps(v, ensure_ascii=False):
                        continue
                    newd[k] = v
                if len(newd) != len(data[key]):
                    print(f"Removidas {len(data[key]) - len(newd)} entradas em: {key}")
                    data[key] = newd
                    modified = True

    # Case 2: top-level list (vector store / episodes list)
    elif isinstance(data, list):
        before = len(data)
        newlist = []
        for item in data:
            try:
                txt = item.get("text", "") if isinstance(item, dict) else json.dumps(item, ensure_ascii=False)
            except Exception:
                txt = str(item)
            if needle in txt:
                continue
            newlist.append(item)
        if len(newlist) != before:
            print(f"Removidas {before - len(newlist)} entradas na lista que continham '{needle}'")
            data = newlist
            modified = True

    else:
        print("Formato de arquivo inesperado:", type(data))
        sys.exit(1)

    if not modified:
        print("Nenhuma entrada encontrada com:", needle)
        sys.exit(0)

    # Backup original file
    bak = mem_path + ".bak"
    shutil.copy2(mem_path, bak)

    # Write updated data
    with open(mem_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("Backup salvo em:", bak)
    print("Arquivo de memória atualizado:", mem_path)


if __name__ == "__main__":
    main()
