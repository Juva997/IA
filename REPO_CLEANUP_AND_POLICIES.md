REPO: Limpeza, Estrutura e Políticas
====================================

Resumo (achados imediatos)
- Ambiente virtual comprometido: `.venv_profiler/` (muitas dependências).
- Binário grande: `vs_BuildTools.exe` na raiz.
- Logs rastreados: `logs/` e vários `benchmark/*.log`.
- Perfis/traces: `profile.prof`, `pyspy_flame.svg`.
- Caches locais: `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/` (presentes).
- Arquivos temporários: `tmp_*`, `tmp_test_runs/`, etc.

Ações imediatas (recomendações e comandos)
1) Atualizar `.gitignore` (já aplicado).
2) Remover do index (untrack) sem apagar localmente:

```bash
# remover do index (sem apagar local)
git rm -r --cached .venv_profiler
git rm --cached vs_BuildTools.exe
git rm -r --cached logs
git rm --cached profile.prof
# commit e push normal
git commit -m "Remove artefatos gerados e ambientes virtuais do repositório"
git push origin HEAD
```

3) Limpar histórico (opcional, necessário para redução drástica do tamanho):
- Usar BFG (fácil):

```bash
# usar BFG (requer Java)
java -jar bfg.jar --delete-folders .venv_profiler --delete-files vs_BuildTools.exe --delete-files profile.prof --delete-folders logs
git reflog expire --expire=now --all
git gc --prune=now --aggressive
git push --force
```

- Ou usar `git filter-repo` (recomendado para controle fino):

```bash
pip install git-filter-repo
# remover caminhos do histórico
git filter-repo --invert-paths --paths .venv_profiler --paths vs_BuildTools.exe --paths profile.prof --paths logs
# push forçado (coordene com o time)
git push --force
```

AVISO: essas operações reescrevem histórico. Coordene com todos os colaboradores antes de forçar push.

Estrutura de pastas ideal (proposta enxuta)
- README.md
- pyproject.toml | requirements.txt
- src/                -> código Python (módulo principal)
- api/                -> endpoints / schema (separado)
- backend/            -> backend services (se aplicável)
- frontend/           -> front-end app (se aplicável)
- tests/              -> testes automatizados
- docs/               -> documentação (sphinx/mkdocs)
- infra/              -> IaC, k8s, terraform, chart
- scripts/            -> utilitários e scripts de manutenção
- benchmarks/         -> configuração (não resultados grandes; armazenar outputs fora do repo)
- data/               -> amostras pequenas (grandões não versionar)
- .github/            -> workflows CI

Notas:
- Migrar código Python para `src/<package>` reduz problemas de import durante testes.
- Não versionar ambientes virtuais ou dependências instaladas.

Estratégia de versionamento
- Use Semantic Versioning (MAJOR.MINOR.PATCH).
- Armazene a versão única no `pyproject.toml` ou `src/<package>/__init__.py` (`__version__`).
- Geração de tags anotadas:

```bash
git tag -a v1.2.3 -m "Release v1.2.3"
git push origin v1.2.3
```

- Automatizar bump de versão via CI com `bump2version`, `poetry version` ou `semantic-release`.
- Regras:
  - Commits tipo `feat:` -> MINOR; `fix:` -> PATCH; breaking change -> MAJOR.
  - Use Conventional Commits para geração automática de changelogs.

Estratégia de releases
- Fluxo proposto:
  1. Desenvolver em branches `feature/*` ou `fix/*`.
  2. Abrir PR para `develop` (ou diretamente `main` se preferir trunk-based).
  3. No merge, CI executa testes/lint.
  4. Criar tag `vX.Y.Z` (manual ou CI) para release.
  5. GitHub Action detecta tag e faz:
     - Build (wheel/sdist + docker image)
     - Publica artefatos no PyPI e imagens no registro (GitHub Container Registry / Docker Hub)
     - Gera GitHub Release com changelog (conventional-changelog / auto-generated)

- Não salvar artefatos build no repositório; use registries e attachments do Release.

Estratégia CI/CD (resumida)
- CI (pull request):
  - Instalar dependências (usar cache), executar:
    - Pre-commit checks (format, lint, security static checks)
    - Type checking (`mypy`)
    - Unit tests (`pytest`) com cobertura
    - Vulnerability scan (snyk/gh-audit)
- CD (on tag):
  - Build wheel/sdist
  - Build Docker image (tag por versão)
  - Push artefatos para registos configurados
  - Atualizar Release e deploy (se aplicável)

Exemplo GitHub Actions (resumo):
- `.github/workflows/ci.yml` -> runs on PRs, runs tests/lint.
- `.github/workflows/release.yml` -> runs on `push` of tags, builds and publishes.

Melhores práticas e otimizações
- Use `actions/cache` para pip/poetry and docker layers.
- Use artefatos do GitHub Actions para salvar resultados de build temporários.
- Não commitar artefatos binários; publique-os em registries.
- Use `git-filter-repo`/BFG para limpeza de histórico e depois force-push após coordenação.

Próximos passos sugeridos (rápidos)
1. Aplicar `git rm --cached` para os itens listados e commitar.
2. Rodar `git filter-repo` ou BFG para remover do histórico (após aprovações).
3. Adicionar workflows básicos de CI (`.github/workflows/ci.yml`) e release (`release.yml`).
4. Migrar código para `src/` (se desejar) e ajustar imports.

Se quiser, eu posso:
- Gerar os workflows GitHub Actions mínimos (`ci.yml` e `release.yml`).
- Gerar um script com os comandos `git rm` + `git filter-repo` pronto para execução.

---
Arquivo gerado automaticamente pelo assistente. Ajustes finos podem ser aplicados conforme preferência da equipe.
