Patches gerados pelo assistente — revise antes de aplicar.

Arquivos de patch:

- fix-tests-and-safety.patch
  - Correções: `benchmark/repair.py`, `actions/tools/python_tools.py`, `actions/executor.py`, `interfaces/api.py`
  - Objetivo: corrigir comportamento de testes, segurança do sandbox e evitar `print_exc` em ambientes com /tmp restrito.

- feature-state-adapters.patch
  - Conteúdo: commit que adiciona `core/state_interface.py`, `core/state_redis_adapter.py` e ajuste em `bootstrap/container.py`.
  - Origem: commit `945a226` na branch `feature/state-adapters`.

- fix-api-query-threadpool.patch
  - Correção dedicada para `interfaces/api.py` (injeção de engine em `_require_api_key` / priorização de runtime_info).

- refactor-planner-decomposition.patch
  - Rascunho: adiciona arquivos novos (`cognition/prompt_builder.py`, `cognition/plan_parser.py`, `cognition/deterministic_planner.py`) como proposta de decomposição do `Planner`.

Como aplicar um patch localmente (exemplo):

```bash
# aplicar fix-tests-and-safety
git apply patches/fix-tests-and-safety.patch

# aplicar feature (certifique-se de estar na branch correta)
git apply patches/feature-state-adapters.patch
```

Notas:
- Revise os patches antes de aplicar; alguns patches adicionam arquivos novos.
- Se for aplicar um patch que contém commits (formatado via `git show`), prefira `git apply` ou `git am` conforme necessário.
