# Recomendações de atualização de dependências (modernização 2026)

Objetivo: mapear riscos e recomendar atualizações para alinhar o projeto a padrões de 2026.

Arquivos alterados nesta mudança:

- `Dockerfile` — base Python atualizada para 3.12-slim
- `backend/requirements.txt` — pins iniciais para backend
- `dev/mock_ollama/requirements.txt` — pins para testar Pydantic v2

Resumo rápido:
- Foco imediato: runtime Python (Docker), compatibilidade FastAPI / Pydantic, SQLAlchemy 2.x, Redis async client, e imagens Docker não fixadas.
- Em paralelo: front-end Expo/React Native, e bibliotecas ML pesadas (transformers, faiss, trl) que precisam de pins e validação de CVEs.

Categorias

1) Dependências obsoletas
- Expo SDK ~48 (frontend) — versão antiga frente a SDKs lançados pós-2024.
- React Native 0.71.8 — acompanhar atualização do Expo.

2) Dependências com risco de segurança / supply-chain
- Imagens não fixadas em `docker-compose.yml` (ex.: `prom/prometheus:latest`) — risco de mudança/distribuição maliciosa.
- Dependências não-pinned no `requirements.txt` (root) — aumenta risco de CVE indetectadas em builds reproduzíveis.

3) Dependências abandonadas / legadas
- `aioredis` no código (adapter protótipo) — projeto foi consolidado no `redis` (redis-py) e `aioredis` é considerado legada.

4) Dependências substituíveis / melhorias
- `aioredis` → `redis` (usar `redis.asyncio`) para client async oficial.
- `psycopg2` (se usado) → `psycopg[binary]` (psycopg v3) ou `asyncpg` para operações async.
- SQLAlchemy legacy API → migrar para SQLAlchemy 2.0 style (declarative via `sqlalchemy.orm`).

Tabela priorizada por risco

Dependência Atual | Versão Atual | Versão Recomendada | Motivo
:-- | :--: | :--: | :--
Python (runtime Docker) | 3.11-slim (Dockerfile antigo) | 3.12-slim | Suporte/segurança/performance; base para builds reproduzíveis
FastAPI | 0.95.2 (pinned em dev/mock_ollama) / não-pinned (backend) | >=0.95, idealmente >=0.100 / compatível com Pydantic v2 | Compatibilidade com Pydantic v2, correções e performance
Pydantic | 1.10.11 (dev/mock_ollama) | >=2.0,<3.0 | Pydantic v2 é nova base (melhor performance); exige migração de schemas e imports
SQLAlchemy | não-pinned + uso de API legada (`ext.declarative`) | >=2.0,<3.0 (migrar para estilo 2.0) | Evitar depreciações; adotar 2.0 ORM idiomático
Alembic | não-pinned | >=1.10 (compatível com SQLAlchemy 2.x) | Migrates compatíveis com SQLAlchemy 2.x
Redis client / async | `redis` usado; `aioredis` presente em código | `redis>=4.x` e usar `redis.asyncio` (remover aioredis) | `aioredis` consolidado no redis-py; API oficial e manutenção
PostgreSQL driver | não-pinned (docs indicam PostgreSQL) | `psycopg[binary]` (psycopg v3) para sync e/ou `asyncpg` para async | Driver moderno, suporte e melhor integração com SQLAlchemy 2.x
Docker images em compose | `prom/prometheus:latest` | pin por versão ou digest (ex.: prom/prometheus:2.xx OR digest) | Reprodutibilidade e segurança contra alteração de imagem
Uvicorn | 0.22.0 (pinned em dev/mock_ollama) / unpinned | >=0.22,<1.0 (manter atualizado) | Correções ASGI, segurança e performance
Expo SDK (frontend) | ~48.0.0 | atualizar para SDK suportado atual (>=49/50 conforme releases) | Compatibilidade com iOS/Android recentes e bibliotecas
React Native | 0.71.8 | atualizar para versão compatível com Expo SDK alvo | Evitar conflitos nativos e garantir suporte dispositivo
Dependências ML / heavy | transformers, trl, faiss-cpu, sentence-transformers (não-pinned) | Fixar versões testadas e auditar CVEs | Tamanho e complexidade exigem controle estrito e CI de auditoria

Ações imediatas (prioridade)

- Bloquear imagens Docker base e docker-compose por versão/digest.
- Fixar (pin) versões críticas no `backend/requirements.txt` e no `dev/mock_ollama/requirements.txt` (feito nesta alteração como ponto inicial).
- Adicionar CI jobs: `pip-audit` / `safety` e `npm audit` para frontend.

Migração Pydantic v1 → v2 (resumo rápido)

- Revisar usos de `BaseModel` e `Field` — alguns argumentos mudaram; `typing` e `Annotated` são recomendados.
- Atualizar validações customizadas e `Config` → nova configuração `model_config` em v2.
- Atualizar dependências (FastAPI compatível) e rodar testes unitários; migrar em pequenos passos (service-by-service).

Migração SQLAlchemy 1.x → 2.x (resumo rápido)

- Adotar `from sqlalchemy.orm import declarative_base` e `sqlalchemy.future`/estilo 2.0 para sessions.
- Atualizar código que usa `engine.connect()`/`sessionmaker()` conforme guia oficial; rodar migrations Alembic com `alembic revision --autogenerate` e validar.

Próximos passos sugeridos (eu posso executar):

1. Gerar PR com estas alterações (pins iniciais e notas) — pronto.
2. Adicionar CI de auditoria (`pip-audit` / `safety`) e obrigar checks.
3. Planejar sprint de migração Pydantic v2 + FastAPI upgrade (criar checklist e testes de regressão).

Se quiser, crio o PR com essas mudanças e adiciono um template de checklist para a migração detalhada (Pydantic/SQLAlchemy). 
