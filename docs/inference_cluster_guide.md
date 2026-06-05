# Guia: Inference Cluster para LLMs (GPU) — Projeto e Operação

Objetivo: projetar e operar um cluster de inference capaz de atender requisitos de
baixa-latência e alto-throughput para modelos LLM (multi-tenant, escalável,
com políticas de fallback e observabilidade).

Resumo rápido:
- Use uma arquitetura com dispatcher (router) + pool de servidores de inference (GPU)
- Para throughput/latência de LLM, recomendo avaliar **vLLM** (alto throughput, batching)
  e **NVIDIA Triton** (controle fino + TensorRT) dependendo do formato do modelo.

1) Arquitetura de referência

```mermaid
graph LR
  User[API Gateway / Client] --> Router[Inference Router / Dispatcher]
  Router --> Cache[Response Cache (Redis)]
  Router --> Queue[Batching Queue]
  Queue --> BatchSvc[Batching Service]
  BatchSvc --> GPUPool[GPU Inference Pool]
  GPUPool --> ModelStore[Model Artifact Store (S3)]
  GPUPool --> Metrics[Prometheus / DCGM]
  Router --> Fallback[Smaller Model Pool]
```

Componentes:
- **Inference Router/Dispatcher**: agrupa requisições por modelo/token-len e encaminha para o serviço de batching. Implementa auth, rate-limit e quotas.  
- **Batching Service**: acumula requisições para formar batches eficientes (max_batch_size, max_latency_ms).  
- **GPU Pool**: pods/instances com GPU (A100/H100) executando o runtime (vLLM, Triton, FastAPI+vLLM).  
- **Model Store**: S3 / artifact registry para modelos; versões imutáveis.  
- **Cache**: Redis para respostas e para embeddings ou prompts com alta reusabilidade.

2) Opções de runtime (prós/contras)
- **vLLM**: ótimo batching e scheduling para LLMs; foco em alta taxa e baixa latência para modelos HuggingFace.  
- **NVIDIA Triton**: produtivo para modelos otimizados com TensorRT; excelente se converter modelos para TensorRT.  
- **Ray Serve / BentoML / TorchServe**: flexíveis para empacotar lógica, mas dependem de implementação de batching.

3) Tipos de paralelismo e when to use
- **Data parallel**: replicar modelo em múltiplas GPUs (bom para throughput).  
- **Model / Tensor parallel**: necessário para modelos grandes (>70B); usar DeepSpeed / Megatron / HuggingFace + Accelerate.  
- **Pipeline parallel**: dividir o modelo em estágios (uso avançado).

4) Batching e SLOs
- Parâmetros principais: `max_batch_size`, `max_wait_ms` (latency bound), `pad_to_max_length`.
- Trade-off: aumentar batch_size melhora throughput mas aumenta tail latency.
- Estratégia comum: configurar `max_wait_ms` pequeno (e.g., 10–30ms) para manter latência, e usar groups by model+temperature+token-limit.

5) Deploy em Kubernetes
- Use node pools com GPUs; configure `nodeSelector` e `tolerations` para pods de GPU.  
- Instalar NVIDIA device plugin e drivers nos nodes.  
- Use `Deployment`/`StatefulSet` para serviços de inference; configurar `resources.requests` com `nvidia.com/gpu: 1`.

Exemplo (snippet YAML):

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: vllm-gpu
spec:
  replicas: 2
  template:
    spec:
      containers:
      - name: vllm
        image: your-registry/vllm:latest
        resources:
          limits:
            nvidia.com/gpu: 1
```

6) Autoscaling
- K8s HPA não escala natively por GPU; usar soluções:
  - **KEDA** com custom metrics (queue length) para escalar deployment workers.  
  - **Cluster Autoscaler** para aumentar nodes GPU quando houver pending pods.  
  - Autoscale baseado em `prometheus` metrics (GPU util, queue length, request latency).

7) Caching e multilayer tiers
- Tier modelos: `fast` (tiny, CPU), `balanced` (small GPU), `power` (large GPU).  
- Estratégia: primeiro tentar cache (Redis LRU) -> fast model -> balanced -> power.  
- Cache keys: hashed(prompt + model + params + context hash).

8) Model versions, canary e rollout
- Deploy de novas versões como novas `Deployment`/replicasets; usar a mesma estratégia canary (deploy canary local, smoke tests, promote).  
- Automação: CI gera image tags; CD faz canary seguindo mesmos passos usados para o API.

9) Fault tolerance e fallback
- Mecanismos:
  - Circuit breaker no Router: ao detectar alta latência/retry, redirecionar a requests para modelos menores.  
  - Timeouts e retries exponenciais.  
  - Warm pools: mantenha réplicas ociosas para zero-warmup.

10) Observability
- Métricas essenciais: latency p50/p95/p99 per model, tokens/s, GPU utilization, memory usage, batch sizes, queue depth.
- Exportadores: `DCGM-exporter` para métricas GPU, Prometheus para agregação, Grafana dashboards.

11) Segurança
- Models e weights são IP sensíveis: armazene em S3 com KMS e controle de acesso.  
- Endpoint auth: mTLS ou API gateway com JWT; isole endpoints internamente.

12) Cost optimization
- Quantize modelos para int8/4-bit onde aceitável (reduz memória e custo).  
- Use mix de GPUs: instâncias menores para fast models, instâncias grandes para power models e parallel workloads.  
- Offload cold models to CPU or disk-backed serving (Llama.cpp) para uso esporádico.

13) Integração com `LLMClient`
- Atualize `LLMClient` para apontar `base_url` à camada do Router/Dispatcher.  
- Implementar retries, timeouts e metrics (retries, response_time), e feature-flag para `ASSISTENTE_MOCK_ENGINE`.

14) Testes de carga e validação
- Perf tests: medir tokens/s por GPU em workloads reais (varying prompt length).  
- Stress test: gerar latência tail; validar que fallback reduz falhas.

15) Checklist operacional
- Drivers NVIDIA e plugin instalados; node pool exclusivo para GPU; monitoramento GPU; deploy canary; rollback automatizado; backups de modelo.

16) Recomendações finais
- Comece com um pequeno cluster vLLM/Triton para validar SLOs; meça custos e latência; então escale por número de GPUs e shards de vector DB.

---

Arquivo de referência: `docs/inference_cluster_guide.md` adicionado ao repositório.
