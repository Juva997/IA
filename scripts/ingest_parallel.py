#!/usr/bin/env python3
"""
Script de ingestão paralela para Vector DB (Qdrant / Milvus) ou fallback local.

Exemplos:
  python scripts/ingest_parallel.py --driver qdrant --url http://localhost:6333 --collection test --num 10000 --batch-size 512 --workers 8

Este script gera documentos sintéticos se nenhum arquivo for fornecido.
"""
import argparse
import hashlib
import math
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from typing import List, Tuple


def offline_embedding(text: str, size: int = 384):
    # fallback deterministic embedding similar ao PoC
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


def chunked(iterable, size):
    for i in range(0, len(iterable), size):
        yield iterable[i : i + size]


def make_text(i: int):
    return f"document {i} generated for ingestion performance testing"


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--driver", default=os.environ.get("VECTORDB_DRIVER", "local"), help="qdrant|milvus|local")
    p.add_argument("--url", default=os.environ.get("VECTORDB_URL", None))
    p.add_argument("--host", default=os.environ.get("VECTORDB_HOST", None))
    p.add_argument("--port", type=int, default=os.environ.get("VECTORDB_PORT", None))
    p.add_argument("--collection", default=os.environ.get("VECTORDB_COLLECTION", "ingest_test"))
    p.add_argument("--num", type=int, default=10000)
    p.add_argument("--batch-size", type=int, default=512)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--vector-size", type=int, default=int(os.environ.get("EMBEDDINGS_VECTOR_SIZE", 384)))
    p.add_argument("--input-file", default=None, help="arquivo com textos, uma linha por documento (opcional)")
    return p.parse_args()


def main():
    args = parse_args()

    # try to import factory
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

    if args.input_file:
        with open(args.input_file, "r", encoding="utf-8") as f:
            texts = [line.strip() for line in f if line.strip()]
    else:
        texts = [make_text(i) for i in range(args.num)]

    total = len(texts)
    batches = list(chunked(texts, args.batch_size))
    print(f"Iniciando ingestão: total={total} batches={len(batches)} batch_size={args.batch_size} workers={args.workers}")

    start = time.time()

    def upload_batch(batch_idx_batch):
        batch_idx, batch = batch_idx_batch
        items = []  # list of tuples (id, text, metadata, vector)
        for t in batch:
            items.append((None, t, {}, None))
        try:
            vs.upsert_batch(items)
        except Exception as e:
            print(f"batch {batch_idx} failed: {e}")

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        for i, batch in enumerate(batches):
            ex.submit(upload_batch, (i, batch))

    duration = time.time() - start
    print(f"Ingestão concluída em {duration:.2f}s — approx {total/duration:.2f} items/s")


if __name__ == "__main__":
    main()
