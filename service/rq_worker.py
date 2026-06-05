"""Entrypoint RQ worker para docker-compose.

Uso:
  python -m service.rq_worker

Este módulo inicializa uma conexão Redis e executa um worker RQ
escutando a fila `default`.
"""
import os
import logging


def main():
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")

    try:
        from redis import Redis
        from rq import Worker, Queue
    except Exception as e:
        logging.error("Dependências 'rq' ou 'redis' não estão disponíveis: %s", e)
        return

    try:
        conn = Redis.from_url(redis_url)
    except Exception as e:
        logging.error("Falha ao conectar no Redis (%s): %s", redis_url, e)
        return

    # Import tasks module so RQ can find task functions by name
    try:
        import integrations.worker_tasks  # noqa: F401
    except Exception:
        logging.debug("Não foi possível importar integrations.worker_tasks; continue mesmo assim")

    # Evita depender de `Connection` no topo do pacote; passamos a conexão
    # explicitamente tanto para as filas quanto para o Worker, compatível
    # com versões do `rq` que exigem `connection` no construtor de Queue.
    queues = [Queue("default", connection=conn)]
    worker = Worker(queues, connection=conn, name=os.environ.get("RQ_WORKER_NAME", "rq-worker"))
    logging.info("Iniciando RQ worker queues=%s, redis=%s", [q.name for q in queues], redis_url)
    worker.work()


if __name__ == "__main__":
    main()
