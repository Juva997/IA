# Security Audit - Resumo Inicial

Principais achados:

- Sandbox e execução de código (`actions/tools/python_tools.py`): boa cobertura via AST, `SAFE_MODULES`, `SAFE_BUILTINS` e execução em processo isolado. Observações:
  - Limites de recursos (`resource.setrlimit`) aplicados apenas em POSIX (não em Windows). Em produção Linux, recomendo reforçar com cgroups/containers e seccomp.
  - `open` sandboxed usa `SANDBOX_ALLOW_FILE_WRITE` flag — verificar política padrão em produção.

- Patch application (`benchmark/repair.py` + `actions/executor.py`): medidas de segurança sólidas:
  - validação de path com `relative_to` (protege path traversal);
  - por padrão `.py` não permitido em patches salvo ativação explícita (`ASSISTENTE_ALLOW_PY_PATCHES`).
  - publicação de patches desativada por default (`ASSISTENTE_PUBLISH_PATCHES`).

- Riscos remanescentes e recomendações:
  - Secrets: garantir `ASSISTENTE_ENFORCE_CONFIG=1` em produção para falhar rápido quando `SECRET_KEY` ou `ASSISTENTE_API_KEY` não estiverem definidos.
  - Prompt injection: adicionar validação/escaping e política de prompt templates com placeholders, bem como detecção de respostas contendo instruções perigosas.
  - Sandbox escape: revisar SAFE_MODULES e BLOCKED_ATTRS regularmente; considerar execução em containers com FS read-only e rede restrita.
  - Command injection em `system_tools` e ferramentas que manipulem `subprocess` — aplicar whitelists e validação estrita de argumentos.

  Correções aplicadas nesta rodada relevantes para segurança:

  - `actions/tools/python_tools.py`: `SANDBOX_ALLOW_FILE_WRITE` padrão alterado para `0` (desabilitado). Isso reduz risco de modificação persistente do workspace por código sandboxed. Para compatibilidade de testes, `tests/conftest.py` habilita escrita durante a suíte de testes.
  - `integrations/llm_client.py`: adicionado circuito-breaker com limiar configurável e duração de abertura, além de retries exponenciais e jitter. Isso evita chamar repetidamente um endpoint LLM indisponível e reduz risco de saturação/DoS.
  - `workers/redis_worker.py` e `integrations/worker_tasks.py`: PoC de workers que promovem isolamento das execuções perigosas (exec Python, apply_patch) dentro de processos/contêineres separados.

Correções aplicadas automaticamente nesta rodada:
- `apply_llm_patches` já restringe `.py` por padrão; não alterado.
- Adicionada resiliência ao `vector_store` (faiss) para proteger contra falhas I/O.
- `Cache` tornado thread-safe para reduzir risco de corrupção de dados em concorrência.

Checklist de ações recomendadas (prioritizadas):
- P0: Habilitar `ASSISTENTE_ENFORCE_CONFIG=1` em produção para checagem de `SECRET_KEY` e `ASSISTENTE_API_KEY`.
- P0: Executar componentes potencialmente perigosos (exec Python, LLM patch apply) em containers com políticas de rede e FS restritas.
- P1: Integrar scanner de segredos (pre-commit / CI) e rotinas de expurgo de logs sensíveis.
- P1: Forçar validação adicional em `write_file`/`apply_patch` para evitar sobrescrever arquivos sensíveis do sistema.
# SECURITY AUDIT

Resumo de verificações de segurança e correções aplicadas/necessárias.

## Itens auditados

- Execução de código Python (`actions/tools/python_tools.py`): o sandbox faz validação AST e usa subprocesso; atenção para escapamentos via `__import__`, atributos dunder e modos de arquivo.
- Path traversal: `safe_open` em `python_tools` já verifica commonpath, bom controle.
- Prompt injection / LLM: recomenda-se sanitizar prompts quando incorporar user-controlled content em system prompts.
- Command injection: `Executor` deve validar ações; `guard` e `_SecurityManager` já fazem validações, manter regras estritas.
- Secrets exposure: `python_tools` limpa variáveis de ambiente na execução do worker (boa prática já implementada).

## Correções aplicadas automaticamente

- Limitação de concorrência no endpoint `/query` para reduzir superfície de DoS e exaustão de threads.

## Recomendações (não aplicadas automaticamente)

1. Auditar `SandboxValidator` com fuzzing e testes de escape.
2. Executar `run_python` em worker com política de recursos (cgroups) e limites de tempo e memória (já parcial).
3. Encriptar secrets em config e usar secret manager.
