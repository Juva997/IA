#!/usr/bin/env python3
"""
Benchmark simples para medir latência/throughput de buscas no Vector DB.

Exemplo:
  python scripts/benchmark_vector_db.py --driver qdrant --collection test --queries 1000 --concurrency 16

O script supõe que dados já foram ingeridos.
"""
import argparse
import os
import random
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--driver", default=os.environ.get("VECTORDB_DRIVER", "local"))
    p.add_argument("--url", default=os.environ.get("VECTORDB_URL", None))
    p.add_argument("--host", default=os.environ.get("VECTORDB_HOST", None))
    p.add_argument("--port", type=int, default=os.environ.get("VECTORDB_PORT", None))
    p.add_argument("--collection", default=os.environ.get("VECTORDB_COLLECTION", "ingest_test"))
    p.add_argument("--queries", type=int, default=1000)
    p.add_argument("--concurrency", type=int, default=8)
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument("--vector-size", type=int, default=int(os.environ.get("EMBEDDINGS_VECTOR_SIZE", 384)))
    return p.parse_args()


def offline_embedding(text: str, size: int = 384):
    import hashlib as _hash

    vec = [0.0] * size
    tokens = [t for t in (text or "").lower().split() if t]
    if not tokens:
        vec[0] = 1.0
        return vec
    for token in tokens:
        d = _hash.sha256(token.encode("utf-8")).digest()
        idx = int.from_bytes(d[:4], "big") % size
        sign = 1.0 if d[4] % 2 == 0 else -1.0
        vec[idx] += sign
    return vec


def main():
    args = parse_args()

    try:
        from memory.vector_store_client import create_vector_store
        try:
            from bootstrap.container import offline_embedding as container_offline
            embedding_fn = container_offline
        except Exception:
            embedding_fn = lambda t: offline_embedding(t, size=args.vector_size)
    except Exception as e:
        print("Failed to import vector_store_client:", e)
        sys.exit(1)

    vs = create_vector_store(embedding_fn=embedding_fn, driver=args.driver, url=args.url, host=args.host, port=args.port, collection=args.collection, vector_size=args.vector_size)

    # Prepare random queries. If the vector store has a method to fetch stored texts, the user
    # can replace this logic. Here we synthesize queries to mimic real-world prompts.
    queries = [f"document sample {random.randint(0, 1000000)}" for _ in range(args.queries)]

    latencies = []
    errors = 0
    start = time.time()

    def run_query(q):
        t0 = time.perf_counter()
        try:
            res = vs.search(q, top_k=args.top_k)
            dur = (time.perf_counter() - t0) * 1000.0
            return dur, True
        except Exception:
            return None, False

    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futures = [ex.submit(run_query, q) for q in queries]
        for fut in as_completed(futures):
            dur, ok = fut.result()
            if not ok or dur is None:
                errors += 1
            else:
                latencies.append(dur)

    total_time = time.time() - start
    total = len(queries)
    done = len(latencies)
    qps = done / total_time if total_time > 0 else 0.0

    print(f"Queries: {total}, Successful: {done}, Errors: {errors}, Duration: {total_time:.2f}s, QPS: {qps:.2f}")
    if latencies:
        print(f"Latency ms: p50={statistics.quantiles(latencies, n=100)[49]:.2f} p95={statistics.quantiles(latencies, n=20)[18]:.2f} p99={sorted(latencies)[int(len(latencies)*0.99)]:.2f}")
        print(f"Mean={statistics.mean(latencies):.2f} ms, Median={statistics.median(latencies):.2f} ms")


if __name__ == "__main__":
    main()
