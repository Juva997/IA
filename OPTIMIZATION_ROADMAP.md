# Optimization Roadmap

Prioridade e próximas ações (curto/médio prazo):

- P0 (Crítico)
  - Corrigir inconsistências de dimensão de embedding (`bootstrap/container.py`) — **APLICADO**.
  - Limitar uso de memória do vector store e implementar políticas de evicção / migrar para vector DB.
  - Forçar configurações de segurança em produção (`ASSISTENTE_ENFORCE_CONFIG`).
  - Implementar circuit-breaker avançado + retries + timeouts no `LLMClient` (APLICADO: `integrations/llm_client.py`).
  - Isolar execuções perigosas em workers dedicados e filas (PoC criado: `workers/redis_worker.py`, `integrations/worker_tasks.py`).

- P1 (Alto)
  - Tornar caches thread-safe e com limites (APLICADO em `utils/cache.py`).
  - Tornar FAISS I/O resiliente e fallback para numpy (APLICADO em `memory/vector_store.py`).
  - Instrumentar métricas de latência, QPS e uso de memória por componente (Prometheus + OTel).

- P2 (Médio)
  - Desacoplar chamadas a LLM em workers assíncronos com fila (Redis/RQ/Celery).
  - Melhorar pool de conexões para DBs e LLM clients.
  - Adicionar TTL e deduplicação de prompts para reduzir chamadas redundantes ao LLM.

- P3 (Baixo)
  - Otimizações de CPU: vetorização em batch de textos quando inserir múltiplos elementos.
  - Compactar/serialize vetores para reduzir footprint em disco/rede.

Validação e testes:
- Cada alteração crítica deve ser aplicada em branch separado com testes unitários e integração.
- Adicionar testes de carga sintética e verificar métricas antes/depois de cada alteração P0/P1.
# OPTIMIZATION ROADMAP

Plano priorizado de otimizações e próximos passos para implementação segura.

## P0 (Crítico)
- Limitar concorrência de `engine.run` (implementado).
- Migrar armazenamento de sessão/memory para serviço (Redis/Postgres).

## P1 (Alto)
- Offload de tarefas pesadas (`run_python`, `apply_patch`, `pytest`) para workers (Celery/RQ/Kafka).
- Vector DB dedicado (Milvus/Pinecone) e FAISS tuning.
- Migrar SQLite → Postgres / PgBouncer.

## P2 (Médio)
- Implementar tracing (OpenTelemetry) e métricas mais detalhadas.
- Otimizar LLM calls: batching, caching, circuit-breakers avançados.

## P3 (Baixo)
- Micro-optimizações no código do engine, pruning mais agressivo de memória.

## Próximos passos imediatos
1. Executar testes unitários e de integração.
2. Criar proof-of-concept de workers (Redis queue + worker para run_python).
3. Provisionar Postgres gerenciado em staging e migrar dados.
