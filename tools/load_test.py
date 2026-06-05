"""Simple load tester for the local Assistente API.

Usage:
    python tools/load_test.py --url http://127.0.0.1:8000/query --concurrency 10 --requests 100

Sends concurrent POST /query requests with a small payload.
"""
import argparse
import time
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests


def do_request(url, payload, timeout=10):
    try:
        r = requests.post(url, json=payload, timeout=timeout)
        return r.status_code, r.text
    except Exception as e:
        return None, str(e)


def run(url, concurrency=5, total_requests=50):
    payload = {"goal": "Olá, me dê um sumário curto"}
    start = time.time()
    results = []
    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        futures = [ex.submit(do_request, url, payload) for _ in range(total_requests)]
        for f in as_completed(futures):
            results.append(f.result())
    duration = time.time() - start
    successes = sum(1 for s, _ in results if s == 200)
    failures = len(results) - successes
    print(f"Total: {len(results)}, Success: {successes}, Fail: {failures}, Duration: {duration:.2f}s")
    return results


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://127.0.0.1:8000/query")
    p.add_argument("--concurrency", type=int, default=5)
    p.add_argument("--requests", type=int, default=20)
    args = p.parse_args()
    run(args.url, concurrency=args.concurrency, total_requests=args.requests)
