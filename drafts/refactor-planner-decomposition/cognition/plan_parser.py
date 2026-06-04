import json
from typing import Any, List


def parse_plan(response: Any) -> List[dict]:
    """Rascunho de PlanParser.

    Tenta transformar a resposta do LLM em uma lista de passos (plan).
    Estratégia inicial: tentar JSON loads; se falhar, retornar lista vazia.
    """
    try:
        if isinstance(response, str):
            return json.loads(response)
        if isinstance(response, list):
            return response
    except Exception:
        return []
    return []
