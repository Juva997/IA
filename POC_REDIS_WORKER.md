PoC: Redis + Workers (RQ / simple consumer)

Este repositório já contém duas abordagens PoC para offload de workloads pesadas:

- `workers/redis_worker.py`: consumer simples que lê a lista Redis `assistant:jobs` (BLPOP) e executa tasks definidas em `integrations.worker_tasks`.
- `integrations/worker_tasks.py` + `integrations/queue_client.py`: integração com `rq` (se `rq` estiver instalado) que enfileira tasks `run_python_task` e `engine_run_task`.
- `service/rq_worker.py`: entrypoint para iniciar um worker RQ via `python -m service.rq_worker` (usado por `docker-compose.yml`).

Como rodar local (rápido):

1) Pré-requisitos locais:
   - Docker e docker-compose ou Docker Desktop.

2) Subir serviços com docker-compose (repositório já inclui `docker-compose.yml` com serviços `redis` e `rq_worker`):

```bash
# sobe os containers, rebuild se necessário
docker compose up --build
```

3) Enfileirar um job de exemplo (em Python local):

```bash
python - <<'PY'
from integrations.queue_client import enqueue_run_python
job = enqueue_run_python({"code": "print(\"hello from job\")"}, state={})
print('job:', getattr(job, 'id', getattr(job, 'get_id', lambda: job)()))
PY
```

4) Alternativa (consumer simples): rode `workers/redis_worker.py` localmente apontando `REDIS_URL` para o Redis do compose:

```bash
export REDIS_URL=redis://localhost:6379/0
python workers/redis_worker.py --redis $REDIS_URL
```

Notas:
- `docker-compose.yml` já contém um serviço `rq_worker` que executa `python -m service.rq_worker`.
- As imagens usam o `Dockerfile` do projeto; elas instalarão as dependências listadas em `requirements.txt` (inclui `redis` e `rq`).
- Para integração de produção, considere usar `rq` + `rq-dashboard` ou migrar para Celery/RabbitMQ, ou um sistema de jobs gerenciado.
