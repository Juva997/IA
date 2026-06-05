"""
Start an RQ worker for the project (PoC).

Usage:
  python scripts/rq_worker.py [queue_name]

Environment variables:
  REDIS_URL - Redis connection URL (default: redis://localhost:6379/0)
  ASSISTENTE_QUEUE_NAME - default queue name (default: default)
"""
import os
import sys

def main():
    try:
        from redis import Redis
        from rq import Worker, Queue, Connection
    except Exception as e:
        print("rq/redis não estão instalados: ", e)
        sys.exit(1)

    redis_url = os.environ.get("REDIS_URL") or "redis://localhost:6379/0"
    default_queue = os.environ.get("ASSISTENTE_QUEUE_NAME") or "default"
    queues = [default_queue]
    if len(sys.argv) > 1:
        queues = sys.argv[1:]

    conn = Redis.from_url(redis_url)
    q_objs = [Queue(name, connection=conn) for name in queues]

    with Connection(conn):
        worker = Worker(q_objs)
        print(f"Iniciando worker RQ nas filas: {queues} (redis={redis_url})")
        worker.work()


if __name__ == "__main__":
    main()
