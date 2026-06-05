# Architecture Review - Resumo

Mapeamento rápido dos componentes encontrados:

- Backend API: [backend/app/main.py](backend/app/main.py) — FastAPI com rotas básicas de autenticação e vocabulário.
- Database: [backend/app/database.py](backend/app/database.py) — SQLAlchemy com `DATABASE_URL` (sqlite por padrão). Pool configurado para DBs não-sqlite.
- Engine: [core/engine.py](core/engine.py) — loop controlador que integra agent, planner, memory, executor e critic.
- Executor e Actions: [actions/executor.py](actions/executor.py), [actions/registry.py](actions/registry.py) — execução de ferramentas, apply-patch flow e integração com queue (RQ).
- Sandbox / Run Python: [actions/tools/python_tools.py](actions/tools/python_tools.py) — execução isolada via `multiprocessing` + AST validation.
- Memory/Vector Store/Retriever: [memory/memory.py](memory/memory.py), [memory/vector_store.py](memory/vector_store.py), [memory/retriever.py](memory/retriever.py).
- LLM Client: [integrations/llm_client.py](integrations/llm_client.py) — requests.Session com retry/circuit-breaker simples e cache.
- Observability: [monitor/metrics.py](monitor/metrics.py) + [integrations/otel.py](integrations/otel.py) (PoC OpenTelemetry + Prometheus metrics)

Pontos fortes:
- Projeto modular com separação clara de responsabilidades (agent/planner/executor).
- Segurança com várias camadas (exec sandboxing, validação de patches, bloqueios por default para .py em apply_llm_patches).
- Observability PoC já presente (Prometheus e OpenTelemetry helpers).

Riscos arquiteturais e oportunidades:
- Memória em processo para vetores (VectorStore) não escala — precisa migrar para vector DB para >10k usuários.
- Uso misto de sync/blocking I/O (requests, subprocess) no caminho de execução do engine — considerar async/worker offload para throughput.
- Estado persistido (memory persist_path) depende de arquivos locais — migrar para armazenamento durável (S3 + vector DB) para HA.

Recomendações rápidas:
- Definir claramente ambiente de produção: usar PostgreSQL, Redis (para state/queue) e um vector DB gerenciado.
- Extrair responsabilidades pesadas (LLM calls, exec Python) para workers assíncronos com filas.
- Adotar limites e monitoramento para vector store e caches.
# ARCHITECTURE REVIEW

Visão geral da arquitetura atual e recomendações práticas.

## Componentes principais

- API layer: `interfaces/api.py` (FastAPI)
- Core engine: `core/engine.py` (síncrono / CPU-bound loop)
- Executor/Actions: `actions/executor.py`, registry, ferramentas em `actions/tools`
- Memory & Retriever: `memory/memory.py`, `memory/vector_store.py`, `memory/retriever.py`
- LLM integration: `integrations/llm_client.py`
- Persistence: `backend/app/database.py` (SQLite por padrão)

## Pontos fortes

- Projeto modular, com componentes separados (Executor, Registry, Memory).
- Possui abstrações para troca de components (VectorStore, LLMClient, StateManager).

## Principais fraquezas

- `AutonomousEngine` é executado de forma síncrona e realiza muitas operações bloqueantes.
- Ferramentas pesadas (`run_python`, `apply_patch`) podem bloquear o fluxo principal.
- Memory e VectorStore mantêm grandes estruturas em memória sem escala horizontal.

## Recomendações arquiteturais (práticas)

1. Separar responsabilidades:
   - API: stateless, apenas enfileira e retorna resultados rápidos.
   - Workers: executar `engine.run` e tarefas pesadas em pool de workers (k8s deployments ou autoscaling workers).
2. State & memory:
   - Mover vetores para vector DB (Milvus / FAISS em servidor / RedisVector) e facts/episodes para RedisJSON/Postgres.
3. LLMs:
   - Externalizar inference para serviço dedicado (GPU cluster ou provedor) com circuit-breakers e rate-limits.

## Alterações aplicadas automaticamente nesta auditoria

- `core/engine.py`: Isolamento do `session_context` por tarefa e sincronização atômica para compatibilidade com cargas concorrentes ([core/engine.py](core/engine.py#L39-L46), [core/engine.py](core/engine.py#L449-L487)).
- `actions/executor.py`: Troca de `print` por `monitor.logger.Logger` para maior observabilidade e integração com sistemas de logs ([actions/executor.py](actions/executor.py#L6-L13), [actions/executor.py](actions/executor.py#L366-L372)).
- `actions/tools/python_tools.py`: análise de sandbox revisada; a configuração `SANDBOX_ALLOW_FILE_WRITE` permanece configurável via env (recomenda-se desabilitar em produção).
 - `actions/tools/python_tools.py`: análise de sandbox revisada; a configuração `SANDBOX_ALLOW_FILE_WRITE` agora padrão `0` (desabilitado em produção). Testes/CI podem habilitar via env.
 - `integrations/llm_client.py`: reforço de resiliência com circuito-breaker, retries exponenciais e timeouts para reduzir impacto de LLMs indisponíveis.
 - `workers/redis_worker.py` + `integrations/worker_tasks.py` + `integrations/queue_client.py`: PoC para offload de workloads pesadas (run_python, engine.run) usando Redis/RQ ou fila Redis simples.
