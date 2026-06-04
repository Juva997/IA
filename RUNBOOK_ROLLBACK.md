# Runbook: Rollback de Patches e Recuperação Rápida

Objetivo
- Procedimento passo-a-passo para reverter patches aplicados, restaurar o workspace e minimizar downtime.

Princípios
- Nunca edite arquivos manualmente sem versionamento.
- Preferir restauração a partir do controle de versão (`git`) quando disponível.
- Sempre validar correção em uma cópia isolada antes de publicar em produção.

1) Diagnóstico inicial
- Verifique logs do serviço (ex.: `data/logs/errors.jsonl`) e CI para entender falha.
- Identifique o último commit/merge que introduziu as mudanças:

  ```bash
  git --no-pager log --oneline -n 20
  ```

2) Isolar serviço (rodar em modo manutenção)
- Se rodando em Docker Compose:

  ```bash
  docker-compose -f docker-compose.yml down
  ```

- Se for um container único, pare o container apropriado.

3) Reverter mudanças (opção 1 — git)
- Reverter para commit estável conhecido:

  ```bash
  git checkout -- .
  # ou reverter o commit
  git revert <SHA>
  ```

4) Reverter usando backups (opção 2 — se backups gerados)
- Se sua execução de `apply_llm_patches` persistiu backups em disco (recomendado criar `data/backups/<timestamp>.json`):

  ```python
  # exemplo rápido para re-aplicar rollback se backups estiverem salvos como JSON
  import json
  from pathlib import Path
  from benchmark import repair

  bfile = Path('data/backups/2026-06-03-1234.json')
  backups = json.loads(bfile.read_text(encoding='utf-8'))
  errors = repair.rollback_patches('.', backups)
  print('rollback_errors', errors)
  ```

- Se `apply_llm_patches` não salvou backups, use `git` (método mais confiável).

5) Validar localmente (sempre em cópia)
- Crie uma cópia do workspace e rode testes nela antes de publicar:

  ```bash
  python -m venv .venv
  source .venv/bin/activate  # Windows: .venv\Scripts\activate
  pip install -r requirements.txt
  pytest -q
  ```

- Alternativamente, use `tmp` e rode pytest no diretório copiado (mesmo comportamento implementado no executor).

6) Reiniciar serviços
- Após validação, iniciar containers:

  ```bash
  docker-compose up -d --build
  ```

7) Auditoria pós-mortem
- Documente o que foi revertido, timestamps, e ações recomendadas.
- Se necessário, crie um PR com o hotfix e um checklist de verificação em CI para evitar regressão.

Checklist rápido (pré-rollback)
- [ ] Logs coletados
- [ ] Backups identificados
- [ ] Commit estável conhecido
- [ ] Cópia de teste validada

Notas operacionais
- Recomendamos integrar persistência de backups de `apply_llm_patches` em `data/backups/` com nome por timestamp.
- Em ambientes críticos, sempre criar imagem/container temporário para validação (canary) antes de publicar mudanças.

Contato
- Mantenha apontado o responsável pelo deploy e o time de segurança para aprovações manuais durante rollbacks.
