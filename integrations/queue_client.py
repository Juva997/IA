"""
Client helpers para enfileirar tarefas em Redis / RQ (PoC).

Design simples: funções para enfileirar `run_python` e `engine.run`
usando tarefas definidas em `integrations.worker_tasks`.

Uso (ex.):
  from integrations.queue_client import enqueue_run_python
  job = enqueue_run_python(data, state)

Este módulo tenta falhar graciosamente quando `rq`/`redis`
não estão instalados (comportamento de fallback local permanece).
"""
import os
import typing


def _redis_url() -> str:
    return os.environ.get("REDIS_URL") or os.environ.get("ASSISTENTE_REDIS_URL") or "redis://localhost:6379/0"


def queue_driver() -> str:
    return (os.environ.get("ASSISTENTE_QUEUE_DRIVER") or os.environ.get("QUEUE_DRIVER") or "").strip().lower()


def enabled() -> bool:
    return queue_driver() == "rq"


def _get_rq_queue(name: str = "default"):
    try:
        from redis import Redis
        from rq import Queue
    except Exception:
        return None

    redis_url = _redis_url()
    try:
        conn = Redis.from_url(redis_url)
        return Queue(name, connection=conn)
    except Exception:
        return None


def enqueue_run_python(data, state=None, queue_name: str = "default", timeout: int = 60):
    """Enfileira uma execução de `run_python`.

    Retorna o objeto job (RQ) ou None em falha.
    """
    q = _get_rq_queue(queue_name)
    if q is None:
        return None

    try:
        from integrations.worker_tasks import run_python_task
    except Exception:
        return None

    try:
        job = q.enqueue(run_python_task, data, state or {}, job_timeout=timeout)
        return job
    except Exception:
        return None


def enqueue_engine_run(goal, workspace_root=None, queue_name: str = "default", timeout: int = 600):
    """Enfileira uma execução de `engine.run` em um worker.

    O worker irá construir uma nova instância do engine pelo bootstrap
    e executar `engine.run(goal)`. Retorna o job RQ ou None.
    """
    q = _get_rq_queue(queue_name)
    if q is None:
        return None

    try:
        from integrations.worker_tasks import engine_run_task
    except Exception:
        return None

    try:
        job = q.enqueue(engine_run_task, goal, workspace_root, job_timeout=timeout)
        return job
    except Exception:
        return None


def fetch_job_result(job_id: str):
    """Busca o estado/resultado de um job RQ (PoC)."""
    try:
        from redis import Redis
        from rq.job import Job
    except Exception:
        return None

    try:
        conn = Redis.from_url(_redis_url())
        job = Job.fetch(job_id, connection=conn)
        return {"status": job.get_status(), "result": getattr(job, "result", None), "exc_info": getattr(job, "exc_info", None)}
    except Exception:
        return None
