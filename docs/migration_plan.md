# Plano de Migração — PoC → Enterprise

Este documento descreve um plano prático e executável para migrar o repositório PoC atual
para uma arquitetura distribuída de nível Enterprise (suportar 1M usuários, 100k simultâneos,
bilhões de vetores, milhares de exec/min).

## Resumo executivo
- Objetivo: transformar o sistema monolítico/PoC em uma plataforma escalável, resiliente e observável.
- Abordagem: fases incrementais (MVP → V1 → V2 → V3 → Enterprise Scale).

---

## Fases e entregáveis

### MVP (validação operável)
- Tornar a API stateless (containerized) e rodar em k8s (Deployment + Service).
- Externalizar configurações sensíveis via Secrets (Vault/SecretsManager).
- Substituir uso local de Redis por Redis gerenciado (ou cluster) em produção.
- Separar execução pesada do `engine.run` para workers assíncronos via fila (Redis/Kafka).
- Introduzir Vector DB gerenciado local (Qdrant/Milvus) opcionalmente em PoC.
- Observability básica: Prometheus + Grafana + logs centralizados.

Entregáveis MVP no repo:
- `infra/k8s/mvp/api-deployment.yaml`
- `infra/k8s/mvp/worker-deployment.yaml`
- `tests/load/k6/query_test.js`

### V1 (produção inicial)
- Deploy em cluster k8s (EKS/GKE/AKS), autoscaling para API e workers.
- Managed Redis (cluster), Postgres para metadados.
- Migrar VectorStore local para VectorDB sharded (Qdrant/Milvus/Pinecone) e controlar ingestão/retenciones.
- Inference: provisionar modelo(s) em um cluster de inference com batching (ex.: Triton/LLM REST/gRPC).
- Introduzir fila enterprise (Kafka/Pulsar) para eventos de alta taxa.

### V2 (escala regional)
- Sharding de VectorDB por tenant/namespace.
- Multi-AZ/region failover para inference e VectorDB.
- Quotas e rate-limits por tenant.

### V3 (multi-região / otimização)
- Cross-region replication, traffic steering, advanced caching (L2 Cache), cold storage em object storage.
- Otimização de custo: quantização de embeddings, compressão, index pruning.

### Enterprise Scale
- Fleet de GPUs (50–200 GPUs) com orquestração de batch; fabric de VectorDB com dezenas+ shards;
- SRE e operações 24/7, playbooks de DR, testes de caos e capacidade.

---

## Checklist técnico (MVP → V1 cutover)

1. Pre-flight (antes de migrar tráfego)
   - Revisar e externalizar secrets (`ASSISTENTE_API_KEY`, Redis URL, etc.).
   - Instrumentar métricas e tracing (OTel, Prometheus exporters).
   - Backup e snapshot do diretório `data/` e índices locais.

2. Deploy inicial (k8s)
   - Aplicar `infra/k8s/mvp/*` no cluster de staging.
   - Configurar ingress / load balancer.
   - Validar healthchecks `/health` e readiness.

3. Fila e workers
   - Provisionar Redis gerenciado; atualizar `REDIS_URL`.
   - Aumentar réplicas de workers e habilitar HPA com métricas custom (backlog size).

4. VectorDB
   - Provisionar Qdrant/Milvus; criar blueprint de ingestão; migrar dados piloto.
   - Validar latência de busca e throughput.

5. Inference
   - Provisionar 1–2 GPUs para inference; expor endpoint de LLMs com batching.
   - Integrar `LLMClient` para apontar para inference cluster.

6. Cutover
   - Direcionar % de tráfego (canary) para k8s deployment; observar erros e latência.
   - Aumentar gradualmente até 100%.

7. Pós-cutover
   - Ajuste de autoscale, limites de recursos, SLO/SLA e runbook.

---

## Arquivos gerados (neste repositório)
- `docs/migration_plan.md` (este arquivo)
- `infra/k8s/mvp/api-deployment.yaml` — Deployment, Service, HPA (MVP)
- `infra/k8s/mvp/worker-deployment.yaml` — RQ worker Deployment
- `infra/terraform/main.tf` — esqueleto Terraform (provider + placeholders)
- `tests/load/k6/query_test.js` — script de carga K6 para `POST /query`

---

## Como usar o teste de carga (k6)
Instale o `k6` localmente ou use `docker`:

Exemplo (local):

```bash
# executar com 50 VUs por 1 minuto
k6 run tests/load/k6/query_test.js --vus 50 --duration 1m
```

Exemplo (docker):

```bash
docker run --rm -i grafana/k6 run - < tests/load/k6/query_test.js
```

Defina `TARGET_URL` e `ASSISTENTE_API_KEY` por variáveis de ambiente quando necessário.

---

## Recomendações rápidas de tecnologia (Enterprise target)
- Vector DB: Qdrant / Milvus / FAISS sharded (self-hosted) ou Pinecone/Weaviate gerenciado.
- Event bus: Kafka / Pulsar para alta taxa; Redis Streams para simpler patterns.
- Model serving: Triton / TorchServe / custom gRPC REST with batching; usar ort/llm-serving se possível.
- Storage: S3 para blobs e snapshots; Postgres para metadata.
- Secrets: HashiCorp Vault / AWS Secrets Manager.

---

## Métricas e SLIs mínimos
- Latência p95 / p99 do endpoint `/query`.
- Throughput (req/s) por endpoint.
- Backlog de filas (RQ/Kafka partitions lag).
- Uso de GPU / utilização e latência média por modelo.

---

## Passos seguintes sugeridos
1. Criar manifests Kubernetes MVP (já gerados neste commit).
2. Preparar Terraform para provisionar cluster e serviços gerenciados.
3. Configurar CI/CD com pipelines de build, push de imagem e deploy canário.
4. Rodar testes de carga controlados e ajustar autoscaling.

---

Documento gerado automaticamente pelo auditor. Para avançar, responda se deseja que eu:

- gere os manifests de CI/CD (GitHub Actions / Jenkins) e o Terraform completo;
- execute testes de carga locais (se você permitir executar comandos remoto/local). 
