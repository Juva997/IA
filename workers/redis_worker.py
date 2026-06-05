"""PoC de worker que consome a lista `assistant:jobs` em Redis e executa tarefas localmente.

Uso:
  python workers/redis_worker.py --redis redis://localhost:6379/0

Este worker é intencionalmente simples e serve como exemplo de PoC.
"""
import os
import json
import time
import argparse

try:
    import redis
except Exception:
    redis = None


def _redis_conn(url=None):
    if redis is None:
        return None
    url = url or os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    try:
        return redis.from_url(url)
    except Exception:
        try:
            return redis.Redis(host="localhost", port=6379, db=0)
        except Exception:
            return None


def _process_payload(payload):
    t = payload.get("type")
    if t == "run_python":
        try:
            from integrations.worker_tasks import run_python_task
            return run_python_task(payload.get("data"), payload.get("state"))
        except Exception as e:
            return {"status": "error", "error": str(e)}
    elif t == "engine_run":
        try:
            from integrations.worker_tasks import engine_run_task
            return engine_run_task(payload.get("goal"), payload.get("state", {}).get("workspace_root"))
        except Exception as e:
            return {"status": "error", "error": str(e)}
    else:
        return {"status": "error", "error": f"unknown_job_type:{t}"}


def run_loop(redis_url=None, poll_interval=1.0):
    r = _redis_conn(redis_url)
    if r is None:
        print("Redis não disponível; instale redis-py ou configure REDIS_URL")
        return

    print("Worker PoC iniciado; aguardando jobs na lista 'assistant:jobs'")
    while True:
        try:
            item = r.blpop(["assistant:jobs"], timeout=5)
            if not item:
                time.sleep(poll_interval)
                continue

            _, raw = item
            try:
                payload = json.loads(raw)
            except Exception:
                print("payload inválido recebido")
                continue

            print(f"Processando job {payload.get('id')} type={payload.get('type')}")
            res = _process_payload(payload)
            print(f"job {payload.get('id')} result: {res}")
        except KeyboardInterrupt:
            print("Worker interrompido")
            return
        except Exception as e:
            print(f"Erro no loop do worker: {e}")
            time.sleep(poll_interval)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--redis', help='Redis URL', default=None)
    args = parser.parse_args()
    run_loop(args.redis)
