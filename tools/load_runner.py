"""Run continuous load for a duration against /query endpoint.

Usage:
    python tools/load_runner.py --url http://127.0.0.1:8000/query --duration 120 --concurrency 20
"""
import argparse
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests


def worker(url, payload, timeout=5):
    try:
        r = requests.post(url, json=payload, timeout=timeout)
        return r.status_code
    except Exception:
        return None


def run(url, concurrency=5, duration=60):
    payload = {"goal": "Teste de carga contínua"}
    end = time.time() + duration
    total = 0
    successes = 0
    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        futures = []
        while time.time() < end:
            # schedule a batch of tasks
            for _ in range(concurrency * 2):
                futures.append(ex.submit(worker, url, payload))

            # collect completed futures periodically
            while futures and time.time() < end:
                f = futures.pop(0)
                status = f.result()
                total += 1
                if status == 200:
                    successes += 1

    print(f"Duration: {duration}s, Total requests: {total}, Success: {successes}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://127.0.0.1:8000/query")
    p.add_argument("--concurrency", type=int, default=5)
    p.add_argument("--duration", type=int, default=60)
    args = p.parse_args()
    run(args.url, concurrency=args.concurrency, duration=args.duration)
