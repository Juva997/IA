import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from bootstrap.container import build_engine

# Teste específico
test = {
    "name": "listar_arquivos",
    "input": "liste todos os arquivos na pasta atual",
    "expect": "action",
    "verify": {"output_contains_any": ["arquivo", "file", "list"]},
}

engine = build_engine()
result = engine.run(test["input"])
print("Resultado:", result)
print("Status:", result.get("status"))
print("Output:", result.get("output"))