# Sanitização de `patches/` e limpeza de histórico

Resumo: arquivos em `patches/` continham um default inseguro `change-me-secret`. Eu removi o default dos arquivos em `patches/` e adicionei um fail-fast (RuntimeError) nas linhas afetadas para evitar que o código use um segredo fraco por acidente.

A seguir estão comandos recomendados (escolha uma estratégia) para limpar o histórico do Git e rotacionar credenciais.

## 0) Commit local
- Revise as mudanças feitas em `patches/` e em `backend/app/auth.py` e `bootstrap/container.py`.
- Faça commit localmente:

```bash
git add patches/* backend/app/auth.py bootstrap/container.py docs/PATCHES_SANITIZATION_INSTRUCTIONS.md
git commit -m "Sanitize patches: remove default SECRET_KEY; add hardening checks"
```

## 1) Se deseja remover arquivos `patches/*` do histórico inteiro (recomendado se patches forem desnecessários)
- Instale `git-filter-repo` (recomendado):

```bash
pip install git-filter-repo
```

- Remover os arquivos `patches/` do histórico:

```bash
git filter-repo --invert-paths --paths patches/
```

- Forçar push para o repositório remoto (AVISO: reescreve histórico):

```bash
git push --force origin main
```

## 2) Se deseja substituir o texto sensível por um placeholder (manter arquivos, mas redacted)
- Criar um arquivo `replacements.txt` com uma substituição:

```
change-me-secret==>REDACTED_SECRET
```

- Executar:

```bash
git filter-repo --replace-text replacements.txt
git push --force origin main
```

## 3) Alternativa com BFG Repo-Cleaner
- Usar BFG para apagar arquivos ou substituir strings. Veja: https://rtyley.github.io/bfg-repo-cleaner/

## 4) Rotacionamento e revogação
- Se `change-me-secret` ou outra credencial foi usada em produção, rotacione/ revogue imediatamente:
  - JWT signing secret: gerar novo `SECRET_KEY` forte (ex.: `openssl rand -base64 48`) e atualizar runtime.
  - Tokens/keys detectadas: revogar no provedor, rotacionar e auditar uso.

## 5) Proteções preventivas (CI + pre-commit)
- Adicione `gitleaks` no CI e em um hook pre-commit para bloquear commits que contenham secrets.
- Exemplo `pre-commit` config snippet (adicionar `.pre-commit-config.yaml`):

```yaml
repos:
  - repo: https://github.com/zricethezav/gitleaks
    rev: v8.30.1
    hooks:
      - id: gitleaks
        args: [--verbose]
```

## 6) Observações
- Operações que reescrevem histórico (`git filter-repo`, BFG) obrigam todos os colaboradores a re-clonar ou rebasear seus forks. Planeje janela de manutenção e comunique time.
- Mantenha backups antes de reescrever e valide o resultado em um clone local.

Se quiser, posso gerar automaticamente o `replacements.txt` ou criar um branch com as mudanças e preparar um PR sugerido (patch). Diga qual abordagem prefere.