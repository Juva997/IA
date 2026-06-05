"""
Adapter Milvus para substituir o VectorStore local.

Interface mínima compatível com `memory.VectorStore`:
 - `add(text, metadata=None)`
 - `search(query, top_k=5)`
 - `upsert_batch(items)` where items is list of (id, text, metadata, vector)
 - `clear()`

Dependências opcionais: `pymilvus`.
"""
import hashlib
import json
import os
from typing import List, Dict, Any


class MilvusVectorStoreAdapter:
    def __init__(
        self,
        embedding_fn,
        host: str = None,
        port: int = None,
        collection: str = "default",
        vector_size: int = 384,
    ):
        self.embedding_fn = embedding_fn
        self.collection_name = collection
        self.vector_size = int(vector_size or 384)
        self.host = host or os.environ.get("VECTORDB_HOST") or os.environ.get("MILVUS_HOST") or "127.0.0.1"
        self.port = port or int(os.environ.get("VECTORDB_PORT") or os.environ.get("MILVUS_PORT") or 19530)

        try:
            from pymilvus import connections, FieldSchema, CollectionSchema, DataType, Collection, utility

            self._connections = connections
            self._FieldSchema = FieldSchema
            self._CollectionSchema = CollectionSchema
            self._DataType = DataType
            self._Collection = Collection
            self._utility = utility
        except Exception as e:  # pragma: no cover - optional dependency
            raise RuntimeError("pymilvus is required for MilvusVectorStoreAdapter: %s" % e)

        # connect
        try:
            self._connections.connect(host=self.host, port=str(self.port))
        except Exception:
            # ignore connect errors here; calls will attempt later
            pass

        # prepare collection
        try:
            if not self._utility.has_collection(self.collection_name):
                fields = [
                    self._FieldSchema(name="id", dtype=self._DataType.INT64, is_primary=True, auto_id=False),
                    self._FieldSchema(name="embedding", dtype=self._DataType.FLOAT_VECTOR, dim=self.vector_size),
                    self._FieldSchema(name="text", dtype=self._DataType.VARCHAR, max_length=65535),
                    self._FieldSchema(name="metadata", dtype=self._DataType.VARCHAR, max_length=65535),
                ]
                schema = self._CollectionSchema(fields, description="vector store")
                self._Collection(self.collection_name, schema)
            self._collection = self._Collection(self.collection_name)
            # create index if missing
            try:
                if not self._collection.has_index():
                    index_params = {"index_type": "HNSW", "metric_type": "IP", "params": {"M": 16, "efConstruction": 200}}
                    self._collection.create_index(field_name="embedding", index_params=index_params)
            except Exception:
                pass
            try:
                self._collection.load()
            except Exception:
                pass
        except Exception:
            # best-effort fallback
            self._collection = None

    def _id_for_text(self, text: str) -> int:
        # deterministic 64-bit id
        h = hashlib.sha1((text or "").encode("utf-8")).digest()[:8]
        return int.from_bytes(h, "big", signed=False)

    def _safe_embed(self, text: str) -> List[float]:
        emb = []
        try:
            emb = list(self.embedding_fn(text) or [])
        except Exception:
            emb = []

        if not emb:
            return []

        if len(emb) != self.vector_size:
            if len(emb) > self.vector_size:
                emb = emb[: self.vector_size]
            else:
                emb = emb + [0.0] * (self.vector_size - len(emb))
        return emb

    def add(self, text: str, metadata: Dict[str, Any] = None):
        if self._collection is None:
            return

        vec = self._safe_embed(text)
        if not vec:
            return

        pid = self._id_for_text(text)
        meta_str = json.dumps(metadata or {})
        try:
            self._collection.insert([[pid], [vec], [text], [meta_str]])
        except Exception:
            pass

    def upsert_batch(self, items: List[tuple]):
        if self._collection is None:
            return
        ids = []
        vecs = []
        texts = []
        metas = []
        for it in items:
            try:
                _id, text, metadata, vector = it
            except Exception:
                continue
            if vector is None:
                vector = self._safe_embed(text)
            if not vector:
                continue
            ids.append(_id or self._id_for_text(text))
            vecs.append(vector)
            texts.append(text)
            try:
                metas.append(json.dumps(metadata or {}))
            except Exception:
                metas.append(json.dumps({"meta": str(metadata)}))

        if not ids:
            return

        try:
            self._collection.insert([ids, vecs, texts, metas])
        except Exception:
            pass

    def search(self, query: str, top_k: int = 5):
        if self._collection is None:
            return []
        qv = self._safe_embed(query)
        if not qv:
            return []
        try:
            search_params = {"metric_type": "IP", "params": {"ef": 64}}
            hits = self._collection.search([qv], "embedding", param=search_params, limit=top_k, output_fields=["text", "metadata"])  # type: ignore
            results = []
            for h in hits[0]:
                payload = {}
                try:
                    payload_text = getattr(h, "_fields", {})
                except Exception:
                    payload_text = {}
                # milvus returns fields in `entity` object depending on version; best-effort parse
                try:
                    text = h.entity.get("text") if hasattr(h, "entity") else None
                except Exception:
                    text = None
                score = float(getattr(h, "distance", getattr(h, "score", 0.0)) or 0.0)
                # fallback: try to extract text from output_fields
                try:
                    row = h.fields
                    text = text or row.get("text")
                except Exception:
                    pass
                # metadata parse
                meta = {}
                try:
                    if hasattr(h, "fields") and "metadata" in h.fields:
                        meta_raw = h.fields.get("metadata")
                        if isinstance(meta_raw, str):
                            meta = json.loads(meta_raw or "{}")
                except Exception:
                    meta = {}

                results.append({"text": text or str(getattr(h, "id", "")), "metadata": meta, "score": score})
            return results
        except Exception:
            return []

    def clear(self):
        try:
            self._utility.drop_collection(self.collection_name)
        except Exception:
            pass
