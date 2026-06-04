"""Critic service protótipo.

Fornece uma interface simples para avaliação de resultados de execução.
"""
from typing import Any, Dict


class CriticEvaluator:
    def __init__(self):
        pass

    def evaluate(self, result: Dict[str, Any]) -> str:
        if not isinstance(result, dict):
            return "fail"
        status = result.get("status")
        if status == "success":
            return "success"
        return "fail"


__all__ = ["CriticEvaluator"]
