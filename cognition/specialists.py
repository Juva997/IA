from actions.registry import ActionRegistry
import subprocess
import re

from integrations.llm_client import LLMClient
from actions.tools import doc_validator
from actions.tools.file_tools import read_file, write_file


class SpecialistRouter:
    def __init__(self):
        self.registry = ActionRegistry()
        self.registry.auto_register()

    def route(self, step, state):
        action = step.get("action")

        # código
        if action in ["run_python", "fix_code"]:
            return self._handle_code(step)

        # web
        if action in ["open_browser", "web_search"]:
            return self._handle_web(step)

        # arquivos
        if action in ["list_files", "read_file"]:
            return self._handle_files(step)

        return self._fallback(step)

    def _handle_code(self, step):
        func = self.registry.get(step["action"])
        return func(step.get("data"))

    def _handle_web(self, step):
        func = self.registry.get(step["action"])
        return func(step.get("data"))

    def _handle_files(self, step):
        func = self.registry.get(step["action"])
        return func(step.get("data"))

    def _fallback(self, step):
        func = self.registry.get(step.get("action"))
        if func:
            return func(step.get("data"))

        return f"no_handler_for: {step}"


def doc_repair(data, state=None):
    """Especialista simples para detectar e reparar docstrings em um arquivo Python.

    Entrada: `data` pode ser uma string com caminho ou um dict com chave `path`.
    Retorno: dicionário compatível com o contrato de ferramentas (status/output/error).
    """
    try:
        # Normaliza entrada
        if isinstance(data, str):
            path = data
        elif isinstance(data, dict):
            path = data.get("path") or data.get("file_path") or data.get("filename")
        else:
            return {"status": "error", "error": "invalid_input"}

        if not path:
            return {"status": "error", "error": "path_missing"}

        # Ler arquivo
        rf = read_file({"path": path}, state)
        if rf.get("status") == "error":
            return rf

        original = rf.get("output") or ""
        source_lines = original.splitlines()

        # Detectar issues
        issues = doc_validator.find_doc_issues(path=path)
        if not issues:
            return {"status": "success", "output": "no_issues_found"}

        client = LLMClient()
        # permitir desabilitar execução de testes via parâmetro (útil para debug)
        run_tests = True
        if isinstance(data, dict) and "run_tests" in data:
            run_tests = bool(data.get("run_tests"))
        applied = []

        # aplicar patches do fim para o começo para preservar índices
        issues_sorted = sorted(issues, key=lambda it: (getattr(it, "lineno", 0) or 0), reverse=True)

        for issue in issues_sorted:
            # snippet para o LLM
            snippet = issue.original if getattr(issue, "original", None) else "\n".join(
                source_lines[max(0, issue.lineno - 3) : min(len(source_lines), (issue.end_lineno or issue.lineno) + 3)]
            )

            prompt = (
                "Você é um assistente que corrige docstrings em Python.\n"
                "Melhore somente a docstring no trecho abaixo.\n\n"
                f"Trecho:\n{snippet}\n\n"
                "Retorne apenas a docstring corrigida entre aspas triplas (ex: \"\"\"Resumo.\"\"\")."
                " Use português. Se houver parâmetros, inclua seção 'Args:'. Não inclua explicações extras."
            )

            llm_resp = client.generate(prompt)

            # limpar resposta do LLM
            suggestion = None
            if isinstance(llm_resp, str) and llm_resp.startswith("[LLM_ERROR]"):
                suggestion = getattr(issue, "suggestion", None)
            else:
                # extrair bloco entre aspas triplas
                m = re.search(r'("""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\')', llm_resp, flags=re.S)
                if m:
                    s = m.group(0)
                    suggestion = s
                else:
                    # fallback: usar todo o texto retornado
                    suggestion = llm_resp.strip()

            if not suggestion:
                applied.append({"issue": issue.message, "applied": False, "reason": "no_suggestion"})
                continue

            # normalizar sugestão (remover fence tripla se presente)
            inner = suggestion.strip()
            mm = re.search(r'^(?:[ruRU]{0,2})?(?:"""|\'\'\')([\s\S]*?)(?:"""|\'\'\')$', inner, flags=re.S)
            if mm:
                inner = mm.group(1).strip()

            # aplicar patch na memória
            issue.suggestion = inner
            start, end, new_lines = doc_validator.generate_patch_for_issue(issue, source_lines)

            if end == 0:
                source_lines = new_lines + [""] + source_lines
            else:
                source_lines = source_lines[: max(0, start - 1)] + new_lines + source_lines[end:]

            applied.append({"issue": issue.message, "applied": True, "name": getattr(issue, "name", None)})

        final_content = "\n".join(source_lines).rstrip() + "\n"

        # backup
        backup_path = f"{path}.bak"
        write_file({"path": backup_path, "content": original}, state)

        # salvar arquivo modificado
        wf = write_file({"path": path, "content": final_content}, state)
        if wf.get("status") == "error":
            return wf

        # rodar testes (pytest) se habilitado
        if run_tests:
            try:
                proc = subprocess.run(["pytest", "-q"], capture_output=True, text=True, timeout=120)
            except Exception as e:
                # tentar rollback
                write_file({"path": path, "content": original}, state)
                return {"status": "error", "error": f"pytest_error: {e}", "applied": applied}

            if proc.returncode != 0:
                # rollback
                write_file({"path": path, "content": original}, state)
                return {
                    "status": "error",
                    "error": "tests_failed",
                    "output": proc.stdout + "\n" + proc.stderr,
                    "applied": applied,
                }

        return {"status": "success", "output": f"applied {len([a for a in applied if a.get('applied')])} patches", "details": applied}

    except Exception as e:
        return {"status": "error", "error": str(e)}
