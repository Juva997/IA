import os


def ingest_codebase(path, memory):
    for root, _, files in os.walk(path):
        for file in files:
            full_path = os.path.join(root, file)

            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    content = f.read()

                memory.vector_store.add(content, {"file": full_path})

            except Exception:
                continue
