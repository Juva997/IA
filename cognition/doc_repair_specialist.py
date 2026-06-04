"""DocRepair specialist: orquestra a detecção de problemas em docstrings
e gera propostas de reparo (patches) usando o validador e opcionalmente LLM.

API principal:
- `DocRepairSpecialist.propose_repairs(path_or_text, use_llm=False)` -> List[dict]

O formato de saída (por item):
{
  "issue": {...},
  "patch": {"start": int, "end": int, "new_lines": [str, ...]},
  "justification": str
}
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional

from integrations.llm_client import LLMClient
from actions.tools.doc_validator import (
    find_doc_issues,
    generate_patch_for_issue,
    issues_to_dicts,
)


def _clean_llm_response(text: str) -> str:
    if not text:
        return ""
    t = text.strip()
    # remove code fences
    t = re.sub(r"^```[a-zA-Z0-9\-]*", "", t)
    t = t.replace("```", "")
    return t.strip()


class DocRepairSpecialist:
    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm = llm_client or LLMClient()

    def propose_repairs(self, path_or_text: str, use_llm: bool = False) -> List[Dict[str, Any]]:
        """Retorna propostas de reparo para o código informado.

        - `path_or_text` pode ser um caminho para arquivo Python ou o conteúdo do arquivo.
        - Se `use_llm` for True, a sugestão será aprimorada por uma chamada ao LLM.
        """
        issues = find_doc_issues(path_or_text)

        # carregar linhas de origem
        if os.path.isfile(path_or_text):
            with open(path_or_text, "r", encoding="utf-8") as fh:
                source = fh.read()
        else:
            source = path_or_text

        source_lines = source.splitlines()
        repairs: List[Dict[str, Any]] = []

        for issue in issues:
            # gerar patch inicial a partir da sugestão do validador
            try:
                start, end, new_lines = generate_patch_for_issue(issue, source_lines)
            except Exception:
                # fallback: inserir sugestão raw
                start, end, new_lines = (
                    getattr(issue, "lineno", 1),
                    getattr(issue, "end_lineno", getattr(issue, "lineno", 1)),
                    [issue.suggestion or ""],
                )

            justification = "auto-generated"

            if use_llm:
                # construir prompt sucinto para o LLM
                context_snippet = issue.original or "\n".join(source_lines[max(0, start - 3) : min(len(source_lines), end + 2)])
                suggested_docstring = "\n".join(new_lines)
                prompt = (
                    f"Você é um especialista em docstrings Python. Melhore a seguinte sugestão de docstring\n"
                    f"Elemento: {issue.name or '<module>'} (tipo={issue.node_type})\n"
                    f"Contexto:\n{context_snippet}\n\n"
                    f"Sugestão atual:\n{suggested_docstring}\n\n"
                    "Forneça apenas a docstring (bloco triple-quoted) com um resumo claro e opcionalmente parâmetros/retorno."
                )

                resp = self.llm.generate(prompt)
                resp = _clean_llm_response(resp)
                if resp:
                    # transformar resposta LLM em linhas
                    new_lines = [line.rstrip("\n") for line in resp.splitlines()]
                    justification = "refined-by-llm"

            repairs.append(
                {
                    "issue": issues_to_dicts([issue])[0],
                    "patch": {"start": start, "end": end, "new_lines": new_lines},
                    "justification": justification,
                }
            )

        return repairs


__all__ = ["DocRepairSpecialist"]
