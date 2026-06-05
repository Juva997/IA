# Performance Audit - Resumo Inicial

Visão geral do que foi feito:
- Revisão focada em backend, engine, executor, workers, memory, retriever, vector store e cliente LLM.
- Identificação e correção automática de problemas seguros e de alta prioridade.

Correções aplicadas (imediatas):

1) Vector size mismatch (P0)
- Arquivo: [bootstrap/container.py](bootstrap/container.py#L393)
- Linha: 393
- Problema: `VectorStore` era criado sem passar `vector_size`, causando inconsistência entre a função de embedding e o índice.
- Impacto: embeddings truncados/padronizados incorretamente; buscas incorretas; perda de qualidade e possíveis exceções.
- Severidade: P0 (Crítico)
- Solução aplicada: passar `vector_size=vector_size` ao criar `VectorStore`.
- Código antes:

```py
vector_store = VectorStore(lambda text: offline_embedding(text, size=vector_size))
```

- Código depois:

```py
vector_store = VectorStore(lambda text: offline_embedding(text, size=vector_size), vector_size=vector_size)
```

2) Cache de embeddings não thread-safe (P1)
- Arquivo: [utils/cache.py](utils/cache.py#L5)
- Linha: 5
- Problema: `Cache` era um dict simples sem travas — risco de race conditions e corrupção sob concorrência.
- Impacto: condições de corrida, perdas de dados de cache, possíveis exceções em cenários concorrentes (workers/threads).
- Severidade: P1 (Alto)
- Solução aplicada: `Cache` passou a usar `threading.Lock()` e suporta `max_items` para evitar crescimento ilimitado.
- Código antes (resumido):

```py
class Cache:
    def __init__(self, ttl=300):
        self.store = {}
        self.ttl = ttl
```

- Código depois (resumido):

```py
class Cache:
    def __init__(self, ttl=300, max_items=None):
        self.store = {}
        self.ttl = ttl
        self.lock = threading.Lock()
        self.max_items = int(max_items) if max_items else None
```

3) FAISS I/O resilience (P1)
- Arquivo: [memory/vector_store.py](memory/vector_store.py#L23)
- Linha: 23, 106, 116
- Problema: falhas de I/O/compatibilidade do FAISS podem quebrar `load()`/`save()`.
- Impacto: exceções em tempo de execução ao carregar índices (ex.: erro de leitura), testes falhando em ambientes com limitações I/O.
- Severidade: P1 (Alto)
- Solução aplicada: `save()` e `load()` envoltos em try/except; em caso de falha o sistema faz fallback para implementação numpy e desativa FAISS.

Validações executadas:
- Testes unitários do `VectorStore` executados localmente — após as correções os testes passaram.

Próximos passos de performance (recomendados):
- Limitar tamanho máximo do `vector_store` em memória e implementar política LRU/evicção (P0).
- Migrar vetorização para um vector DB (Milvus/FAISS em disco, Weaviate, Pinecone) para escala (P0).
- Instrumentar métricas detalhadas (QPS, latência por endpoint, uso de memória do vector store) (P1).

Estimativas de impacto:
- Corrigir `vector_size` resolve problemas de busca semântica de embeddings.
- Cache thread-safe reduz riscos de corrupção sob concorrência.

---
Arquivo gerado automaticamente pela auditoria inicial.
# PERFORMANCE AUDIT

Resumo das análises e mudanças aplicadas automaticamente neste commit.

## Mudanças aplicadas (automáticas)

- `interfaces/api.py`: adicionada limitação de concorrência (`asyncio.Semaphore`) no endpoint `/query` para evitar esgotamento de threads/workers.
- `memory/memory.py`: persistência assíncrona (background thread) para evitar bloqueio de I/O durante execução do `engine`.
- `integrations/llm_client.py`: configurado `HTTPAdapter` com pool e `Retry`; implementado circuito simples para evitar chamadas contínuas a LLM após falhas repetidas.
 - `integrations/llm_client.py`: configurado `HTTPAdapter` com pool e `Retry`; implementado circuito-breaker robusto, retries exponenciais com jitter e timeouts para `generate()` (P0 aplicado). Veja `integrations/llm_client.py` (gerar inicia em ~L94).
 - `workers/redis_worker.py` + `integrations/worker_tasks.py` + `integrations/queue_client.py`: PoC de workers/queue (Redis/RQ) para offload de `run_python` e `engine.run`.
 - `actions/tools/python_tools.py`: `SANDBOX_ALLOW_FILE_WRITE` agora padrão `0` (desabilitado em produção). Testes ajustados para habilitar via `tests/conftest.py`.
- `backend/app/database.py`: configurado `pool_pre_ping` e parâmetros de pool (`DB_POOL_SIZE`, `DB_MAX_OVERFLOW`) quando usar banco não-sqlite.

## Problemas encontrados e impacto estimado (sumarizado)

- Execuções longas do `engine.run` bloqueiam o event loop se não forem isoladas (Impacto: alto). Solução aplicada: semáforo (P0).
- Escrita síncrona de memória e vetores causa latência picos (Impacto: alto). Solução aplicada: gravação em background (P1).
- Chamadas HTTP bloqueantes para LLM sem pooling podem esgotar conexões (Impacto: médio). Solução aplicada: pooling + retry + circuit-breaker leve (P1).
- Uso de SQLite por padrão não escala com concorrência (Impacto: alto em produção). Solução aplicada: habilitação de pool_pre_ping para DBs não-sqlite e instruções de migração (P1).

## Tabela resumida de prioridades

| Problema | Impacto | Complexidade | Prioridade | Ganho Esperado |
|---|---:|---:|---:|---:|
| Engine.run bloqueando | Alto | Médio | P0 | Redução de latência tail e estabilidade |
| Persistência síncrona | Alto | Médio | P1 | Redução de latência e I/O contention |
| LLM sem pooling | Médio | Médio | P1 | Maior throughput de chamadas LLM |
| SQLite em produção | Alto | Médio | P1 | Evita locks de escrita e contenda |

## Observações

As mudanças aplicadas são seguras e reversíveis. Algumas melhorias de maior impacto (fila distribuída, vector DB gerenciado, workers dedicados) estão listadas no roadmap.
