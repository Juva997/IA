"""
Adapter Qdrant para substituir o VectorStore local.

Interface mínima compatível com `memory.VectorStore`:
 - `add(text, metadata=None)`
 - `search(query, top_k=5)`
 - `upsert_batch(items)` where items is list of (id, text, metadata, vector)
 - `clear()`

Dependências opcionais: `qdrant-client`.
"""
import hashlib
import os
from typing import List, Dict, Any


class QdrantVectorStoreAdapter:
    def __init__(
        self,
        embedding_fn,
        url: str = None,
        collection: str = "default",
        vector_size: int = 384,
    ):
        self.embedding_fn = embedding_fn
        self.collection = collection
        self.vector_size = int(vector_size or 384)
        self.url = url or os.environ.get("VECTORDB_URL") or os.environ.get("QDRANT_URL") or "http://localhost:6333"

        try:
            from qdrant_client import QdrantClient
            from qdrant_client.http import models as rest

            self._client = QdrantClient(url=self.url)
            self._rest = rest
        except Exception as e:  # pragma: no cover - optional dependency
            raise RuntimeError("qdrant-client is required for QdrantVectorStoreAdapter: %s" % e)

        # ensure collection exists
        try:
            cols = [c.name for c in self._client.get_collections().collections]
            if self.collection not in cols:
                self._client.recreate_collection(
                    collection_name=self.collection,
                    vectors_config=self._rest.VectorParams(size=self.vector_size, distance=self._rest.Distance.COSINE),
                )
        except Exception:
            # best-effort: try to create
            try:
                self._client.recreate_collection(
                    collection_name=self.collection,
                    vectors_config=self._rest.VectorParams(size=self.vector_size, distance=self._rest.Distance.COSINE),
                )
            except Exception:
                pass

    def _id_for_text(self, text: str) -> str:
        h = hashlib.sha1((text or "").encode("utf-8")).hexdigest()
        return h

    def _safe_embed(self, text: str) -> List[float]:
        emb = []
        try:
            emb = list(self.embedding_fn(text) or [])
        except Exception:
            emb = []

        if not emb:
            return []

        # normalize/resize
        if len(emb) != self.vector_size:
            if len(emb) > self.vector_size:
                emb = emb[: self.vector_size]
            else:
                emb = emb + [0.0] * (self.vector_size - len(emb))

        return emb

    def add(self, text: str, metadata: Dict[str, Any] = None):
        vec = self._safe_embed(text)
        if not vec:
            return

        pid = self._id_for_text(text)
        payload = {"text": text}
        if metadata:
            try:
                payload.update(metadata)
            except Exception:
                payload["meta"] = metadata

        point = self._rest.PointStruct(id=pid, vector=vec, payload=payload)
        try:
            self._client.upsert(collection_name=self.collection, points=[point])
        except Exception:
            # best-effort: swallow errors to maintain behavior similar to PoC
            pass

    def upsert_batch(self, items: List[tuple]):
        """items: list of tuples (id, text, metadata, vector)
        If vector is None it will be computed from text using embedding_fn.
        """
        points = []
        for it in items:
            try:
                _id, text, metadata, vector = it
            except Exception:
                continue

            if vector is None:
                vector = self._safe_embed(text)
            if not vector:
                continue

            payload = {"text": text}
            if metadata:
                try:
                    payload.update(metadata)
                except Exception:
                    payload["meta"] = metadata

            points.append(self._rest.PointStruct(id=_id or self._id_for_text(text), vector=vector, payload=payload))

        if not points:
            return

        try:
            # Qdrant accepts batches
            self._client.upsert(collection_name=self.collection, points=points)
        except Exception:
            # swallow
            pass

    def search(self, query: str, top_k: int = 5):
        qv = self._safe_embed(query)
        if not qv:
            return []

        try:
            hits = self._client.search(collection_name=self.collection, query_vector=qv, limit=top_k, with_payload=True)
            results = []
            for h in hits:
                payload = getattr(h, "payload", {}) or {}
                text = payload.get("text") or payload.get("_text") or None
                # metadata exclude text
                meta = {k: v for k, v in payload.items() if k != "text"}
                results.append({"text": text or str(h.id), "metadata": meta, "score": float(getattr(h, "score", 0.0))})
            return results
        except Exception:
            return []

    def clear(self):
        try:
            self._client.delete_collection(collection_name=self.collection)
            # recreate
            self._client.recreate_collection(
                collection_name=self.collection,
                vectors_config=self._rest.VectorParams(size=self.vector_size, distance=self._rest.Distance.COSINE),
            )
        except Exception:
            pass
