# Checklist de Migração: Pydantic v1 → v2 e SQLAlchemy 1.x → 2.0

Objetivo: orientar uma migração segura e incremental das dependências e do código.

Pré-requisitos
- Criar branch: `migrate/pydantic2-sqlalchemy2`.
- Ter testes unitários e de integração passando (ou cobertura mínima).
- Ter backup/restore do banco de dados (staging/prod).
- Fixar versões de dependências em `requirements` / `backend/requirements.txt` (já iniciado).

Passo 0 — Baseline
- [ ] Rodar suíte de testes atual e registrar falhas existentes.
- [ ] Executar `pip-audit`/`safety` localmente e salvar relatórios.
- [ ] Rodar `rg`/`grep` para localizar padrões que precisarão ser alterados:
  - `rg "model\.dict\(|\.json\(|parse_obj\(|root_validator|@validator|from sqlalchemy.ext.declarative|session.query\("`

Pydantic v1 → v2 (tasks)
- [ ] Atualizar dependências e criar um commit de preparação:
  - `pydantic>=2.0,<3.0` e `fastapi` compatível (por ex. >=0.100.x).
- [ ] Substituir métodos de serialização/validação:
  - `instance.dict()` → `instance.model_dump()`
  - `instance.json()` → `instance.model_dump_json()`
  - `Model.parse_obj(x)` → `Model.model_validate(x)`
- [ ] Migrar validações e validadores:
  - `@validator` (v1) → `@field_validator` / `@model_validator` (v2) conforme necessidade.
  - `root_validator` → `@model_validator(mode='before'|'after')`.
- [ ] Atualizar `Config` → `model_config`:
  - Antes:
    ```py
    class MyModel(BaseModel):
        class Config:
            orm_mode = True
    ```
  - Depois:
    ```py
    from pydantic import ConfigDict

    class MyModel(BaseModel):
        model_config = ConfigDict(from_attributes=True)
    ```
- [ ] Atualizar imports onde necessário (`from pydantic import BaseModel, Field, ConfigDict, field_validator`).
- [ ] Procurar e ajustar usos de `typing.Annotated` e `Annotated`-style metadata quando aplicável.
- [ ] Rodar testes e corrigir regressões por pacote/serviço (migrar incrementalmente por módulo).
- [ ] Opcional: avaliar uso de codemods para acelerar substituições recorrentes (pesquisar ferramentas oficiais/comunitárias antes de rodar).

SQLAlchemy 1.x → 2.0 (tasks)
- [ ] Atualizar `backend/requirements.txt` para `sqlalchemy>=2.0` e `alembic` compatível.
- [ ] Atualizar imports e base declarativa:
  - Antes: `from sqlalchemy.ext.declarative import declarative_base`
  - Depois: `from sqlalchemy.orm import declarative_base`  (ou usar `class Base(DeclarativeBase): pass`)
- [ ] Recomendar definição de base moderna (opcional):
  ```py
  from sqlalchemy.orm import DeclarativeBase

  class Base(DeclarativeBase):
      pass
  ```
- [ ] Migrar padrões de sessão / contexto:
  - Preferir `Session` como context manager:
    ```py
    from sqlalchemy.orm import Session

    with Session(engine) as db:
        ...
    ```
  - Atualizar `get_db()` para `with`-context (evita flush/close manual).
- [ ] Substituir `session.query()` por `select()`/`session.execute()` pattern:
  - `session.query(User).filter_by(...).all()` → `session.execute(select(User).filter_by(...)).scalars().all()`
- [ ] Atualizar consultas complexas e ORM usage (relationships, eager loading) e revalidar performance.
- [ ] Atualizar `alembic/env.py` para importar `target_metadata` do novo `Base` e executar `alembic revision --autogenerate`.

Integração e testes
- [ ] Executar migração em ambiente de testes/staging com snapshot do DB.
- [ ] Executar migrações Alembic geradas e validar schema resultante.
- [ ] Executar suíte de integração que cobre endpoints FastAPI e operações DB.
- [ ] Testar casos de serialização/deserialização entre serviços (JSON contracts).

Rollout
- [ ] Criar checklist de deploy: backup DB, deploy em canary, monitorar erros/telemetria 24-48h.
- [ ] Plano de rollback: manter snapshot do DB e instruções `alembic downgrade` (reverter migrations manualmente testadas).

Ferramentas e comandos úteis
- Procurar ocorrências rapidamente:
  - `rg "model\.dict\(|parse_obj\(|root_validator|@validator|session.query\(" -n`
- Testes e lint:
  - `pytest -q`
  - `ruff .` / `mypy` onde aplicável
- Alembic:
  - `alembic revision --autogenerate -m "sqlalchemy2 migration"`
  - `alembic upgrade head`

Estimativa e estratégia incremental
- Pequeno códigobase (testes robustos): 1–3 dias
- Médio (várias integrações): 1–2 semanas
- Grande (microservices + infra): planejar sprints por serviço

Observações finais
- Migrar primeiro em dev/CI; preferir deploy por serviço/feature-flag quando possível.
- Priorizar segurança: fixe deps e rode auditoria (workflow criado em `.github/workflows/dependency-audit.yml`).

FIM
