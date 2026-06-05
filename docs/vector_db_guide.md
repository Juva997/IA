# Guia de Substituição: Vector DB (Qdrant / Milvus / FAISS-shards)

Objetivo: orientar a migração da solução atual (in-memory / FAISS local) para
um Vector DB distribuído e gerenciável capaz de suportar centenas de milhões
ou bilhões de vetores com baixa latência e alta disponibilidade.

Resumo rápido:
- Recomendados para self-host: **Qdrant** ou **Milvus** (sharding + persistência).  
- Soluções gerenciadas (SaaS): Pinecone, Weaviate Cloud, Milvus Cloud.  
- Para alta densidade on-disk: FAISS em modo IVF+PQ com sharding e armazenamento em NVMe.

Quando migrar:
- Atingir limites de memória local (VECTORSTORE_MAX_ENTRIES).  
- Necessidade de alta disponibilidade, backup, sharding e observabilidade.  

1) Princípios de arquitetura
- Arquitetura típica:

```mermaid
graph TD
  API[API Stateless] --> Router[Vector Router]
  Router -->|shard lookup| VectorDBShard1[VectorDB Shard 1]
  Router --> VectorDBShard2[VectorDB Shard 2]
  Router --> VectorDBShardN[VectorDB Shard N]
  VectorDBShard1 --> ObjectStorage[S3 Snapshots]
  VectorDBShard2 --> ObjectStorage
  VectorDBShardN --> ObjectStorage
  API --> Cache[Redis Cache (embeddings/results)]
```

- Componentes críticos:
  - VectorDB cluster (shards + replicas)
  - Metadata DB (Postgres) para mapear collection → shard
  - Embedding service (serviço separado, cache de embeddings)
  - Router/Coordinator que resolve qual shard consultar
  - Object storage (S3) para snapshots e backups

2) Escolha do banco vetorial — comparativo rápido
- Qdrant: bom equilíbrio, API HTTP/gRPC, suporta HNSW e persistência; fácil de operar.  
- Milvus: muito usado em escala, suporta diversos índices (IVF, HNSW, ANNOY), deployment mais maduro para sharding.  
- FAISS (self-hosted): flexível e rápido; precisa de infra (NVMe), ideal para operações offline e índices customizados.  
- Pinecone / Weaviate Cloud: SaaS com gestão simplificada (bom para acelerar time-to-prod).

3) Tipos de índice e trade-offs
- HNSW: latência baixa, busca por proximidade, porém exige RAM (mantém grafo em memória).  
- IVF + PQ: usa quantização; excelente para escala (reduz memória/latência), exige tuning (nlist, nprobe, m).  
- DiskANN / External indexes: para datasets que não cabem em RAM.

4) Dimensionamento e ordenação de custos
- Tamanho bruto por vetor (float32): vector_dim × 4 bytes. Ex.: 384 × 4 = 1.536 bytes (≈1.5 KB).  
- Para 1B vetores: ≈1.5 TB sem compressão.  
- Com quantização (PQ) você pode reduzir para tipicamente 8–32 bytes por vetor (config dependent).

Regra prática: calcule storage bruto e aplique fator de overhead para índice (x1.5–x5) e replicas.

5) Estratégias de shard/particionamento
- Hash por `tenant_id` (bom para multi-tenant e isolamento).  
- Range/temporal sharding (bom para dados append-only; facilita pruning).  
- Namespace lógico (topic/domain) + consistent hashing para redistribuição.

Recomendações:
- Use routing layer (metadata service) que mantém mapa shard => node(s).  
- Evite shard único por capacidade; planeje re-sharding incremental.

6) Integração com o código atual
- Objetivo: substituir `memory/vector_store.py` por um adapter que mantém a mesma interface
  (`add`, `search`, `save`/`load` opcional). Ideal: criar `memory/vector_store_client.py`.

Exemplo (Qdrant client) — pseudocódigo:

```python
from qdrant_client import QdrantClient
from qdrant_client.http import models as rest

class QdrantVectorStoreClient:
    def __init__(self, url, collection, vector_size=384):
        self.client = QdrantClient(url=url)
        self.collection = collection
        self.vector_size = vector_size
        # criar colecao se não existir
        try:
            self.client.get_collection(collection_name=self.collection)
        except Exception:
            self.client.recreate_collection(
                collection_name=self.collection,
                vectors_config=rest.VectorParams(size=self.vector_size, distance=rest.Distance.COSINE),
            )

    def add(self, id, vector, payload=None):
        point = rest.PointStruct(id=id, vector=vector, payload=payload or {})
        self.client.upsert(collection_name=self.collection, points=[point])

    def search(self, vector, top_k=10):
        hits = self.client.search(collection_name=self.collection, query_vector=vector, limit=top_k, with_payload=True)
        return hits

```

- Integração prática:
  1. Implementar adapter (Qdrant/Milvus) com fallback local para dev.  
  2. Atualizar `bootstrap/container.py` para criar `VectorStore` a partir do adapter se `VECTORDB_ENABLED=true`.  
  3. Atualizar `Retriever` para usar a client search e passar `metadata`/payload para ranking.

7) Migração de dados
- Duas opções:
  - Recomputar embeddings e re-ingest (recomendado quando embeddings evoluem).  
  - Exportar vectors locais (se existentes) e bulk upsert (bom para PoC).  

Passos sugeridos para re-ingest (escala grande):
  1. Provisionar VectorDB com shards e targets de performance.  
  2. Implementar pipeline de ingest em workers (paralelismo controlado, batch upsert).  
  3. Rastrear progresso (checksums/ids) e validar amostras.  
  4. Fazer cutover em modo leitura dual-read (API lê prioritariamente do VectorDB, escreve em ambos).  
  5. Remover fallback local depois de estabilizar.

8) Backup, snapshots e restore
- Snapshot frequente para S3/obj storage.  
- Testar restores em ambiente de staging.  
- Para FAISS offline, mantenha .index + .npz em object storage e reconsidere rebuild em caso de incompatibilidade.

9) Observability e métricas
- Métricas mínimas: qps, p50/p95/p99 latência, index build time, shard size, memory RSS, disk usage, search-latency por top_k.
- Logs de erros e alerta para: node OOM, rebuild fail, high-latency.

10) Segurança e governance
- Isolar endpoints do VectorDB por rede privada (VPC), usar mTLS ou API-key.  
- Aplicar RBAC por namespace/tenant se possível.

11) Testes e validação
- Testes de ingest: medir ingest throughput (vectors/sec), latência por batch.  
- Testes de query: latência p50/p95/p99 para top_k comuns (5, 10, 50).  

12) Boas práticas operacionais
- Batch upserts (ex.: 1k–10k por request) e paralelismo controlado.  
- Configure autoscaling de nós de armazenamento (disks NVMe) baseados em uso.  
- Prefira rede de baixa latência entre API, Embedding service e VectorDB.

13) Checklist mínimo para produção
- TLS entre serviços; RBAC e autenticação; snapshot automático; monitoramento; testes de restauração; deployment multi-AZ.

---

Arquivo de referência: `docs/vector_db_guide.md` adicionado ao repositório.
