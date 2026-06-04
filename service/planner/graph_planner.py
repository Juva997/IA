"""GraphPlanner protótipo (integração conceitual com LangGraph).

Este módulo é um esboço: mostra como organizar a criação de planos como
um grafo de intenções. A integração real com LangGraph deve seguir a API
da biblioteca escolhida; aqui oferecemos um fallback simples.
"""
from typing import Any, Dict, List, Optional


class GraphPlanner:
    def __init__(self, llm_client=None, tool_catalog=None, fallback=None):
        self.llm = llm_client
        self.catalog = tool_catalog
        self.fallback = fallback

    async def create_plan(self, goal: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Gera um plano (lista de passos) a partir de um goal/contexto.

        Estratégia:
        1. Tentar usar LLM+schema (LangGraph) para gerar grafo estruturado
        2. Validar nós do grafo contra o catálogo MCP
        3. Linearizar em passos executáveis
        4. Fallback para planner determinístico simples
        """
        # Tentativa: LLM estrutural (placeholder)
        if self.llm and hasattr(self.llm, "generate_structured"):
            try:
                struct = await self.llm.generate_structured(goal, context)
                steps = self._map_struct_to_steps(struct)
                validated = self._validate_steps(steps)
                if validated:
                    return validated
            except Exception:
                pass

        # Fallback leve: delegar ao planner legacy se fornecido
        if self.fallback:
            try:
                maybe = self.fallback.create_plan(goal, context)
                return maybe
            except Exception:
                pass

        # último recurso: resposta vazia (engine decidirá fallback)
        return []

    def _map_struct_to_steps(self, struct) -> List[Dict[str, Any]]:
        # Conversão dependente do schema de saída do LLM/LangGraph
        # Exemplo (pseudo): [{'node':'write_file','path':'a.py','content':'...'}]
        if not struct:
            return []
        steps = []
        for item in struct.get("nodes", []) if isinstance(struct, dict) else struct:
            action = item.get("action")
            data = item.get("data") or {}
            steps.append({"action": action, "data": data})
        return steps

    def _validate_steps(self, steps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not self.catalog:
            return steps
        validated = []
        for s in steps:
            if self.catalog.get(s.get("action")):
                validated.append(s)
        return validated


__all__ = ["GraphPlanner"]
