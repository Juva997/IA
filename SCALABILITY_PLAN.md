# Scalability Plan (estimativas)

Resumo: estimativas de recursos e recomendações para aumentar capacidade do sistema.

Assumptions:
- Carga média por usuário: 0.2 RPS request direcionada ao engine/LLM; picos menores.
- Latência alvo: <500ms para API leve; LLM calls fora do orçamento de latência serão assincronizados.

Notas: valores aproximados — ajustar após métricas reais (Prometheus + traces).

1) 100 usuários simultâneos
- CPU: 2 vCPU
- RAM: 4 GB
- Workers: 2 worker processes (executor/engine) + 1 API instance
- Banco: PostgreSQL single small (db.t3.small) ou SQLite para dev
- Cache: Redis t3.small ou local process cache
- Vector DB: FAISS local (pequena), persistência em disco
- Custo aproximado (mensal, AWS-like): $50–$150

2) 1.000 usuários simultâneos
- CPU: 4–8 vCPU
- RAM: 8–16 GB
- Workers: 4–8 workers (engine/executor), API scaled to 2–3 instances
- Banco: managed Postgres (db.t3.medium / db.t3.large)
- Cache: Redis (clustered minimal), 1–2 nodes
- Vector DB: Managed or FAISS on dedicated storage (e.g., EBS) / Milvus single node
- Custo aproximado: $300–$1,200

3) 10.000 usuários simultâneos
- CPU: 16–32 vCPU across app cluster
- RAM: 64 GB
- Workers: 16–32 workers (autoscaled), API behind load balancer with autoscaling
- Banco: managed Postgres (db.m5.large / read replicas)
- Cache: Redis cluster
- Vector DB: Sharded vector DB (Milvus / Pinecone / Weaviate managed)
- Custo aproximado: $3k–$12k

4) 100.000 usuários simultâneos
- CPU: 64+ vCPU (distributed cluster)
- RAM: 256+ GB
- Workers: 100+ workers, autoscaling, job queues
- Banco: Highly-available Postgres with read replicas or Citus/Postgres sharding
- Cache: Redis Cluster / ElastiCache
- Vector DB: Managed vector DB with sharding / horizontal scaling (Pinecone / Milvus Enterprise)
- Custo aproximado: $20k–$100k+ (dependente de taxa de LLM calls — custos variam muito)

Recomendações de arquitetura para escala:
- Colocar LLM calls em filas assíncronas e caches de respostas (deduplicação de prompts).
- Offload de execuções de código para workers isolados (containers) com limites de recursos.
- Armazenar vetores em vector DB gerenciado e manter apenas short-term cache local.
- Utilizar observability e autoscaling com thresholds (CPU, latência, LLQ backlog).
# SCALABILITY PLAN

Estimativas e recomendações por faixa de usuários simultâneos.

Notas: as estimativas assumem workload médio por request que envolve uma chamada LLM (externa) e execução do engine. Custos são estimativas genéricas e variam por provedor.

## 1) 100 usuários simultâneos
- CPU: 4 vCPU
- RAM: 8-16 GB
- Workers: API replicas 1-2, engine workers 1-2
- Banco: Postgres small (db.t3.small ou gerenciado equivalente)
- Cache: Redis pequeno
- Vector DB: FAISS local ou RedisVector pequeno
- Custo aproximado: US$50-200/mês

## 2) 1.000 usuários simultâneos
- CPU: 8-16 vCPU (distribuído)
- RAM: 32-64 GB
- Workers: API replicas 3-5, engine workers 4-8
- Banco: Postgres managed with replicas
- Cache: Redis cluster
- Vector DB: Managed (Milvus, RedisVector cluster)
- Custo aproximado: US$500-2.000/mês

## 3) 10.000 usuários simultâneos
- CPU: 64+ vCPU (cluster)
- RAM: 256+ GB
- Workers: API autoscale, engine workers tens (K8s HPA)
- Banco: Postgres cluster or cloud RDS with read replicas
- Cache: Redis cluster (sharded)
- Vector DB: Dedicated cluster (Milvus or Pinecone)
- Custo aproximado: US$5k-20k+/mês

## 4) 100.000 usuários simultâneos
- CPU: multi-region cluster, centenas vCPU
- RAM: TB class memory across nodes
- Workers: large autoscaling fleet, dedicated inference GPUs
- Banco: Sharded, multi-region DB
- Cache: large Redis/Elasticache
- Vector DB: Enterprise vector DB (Pinecone, Milvus, or custom FAISS sharded)
- Custo aproximado: US$50k+/mês (altamente dependente de inference costs)
