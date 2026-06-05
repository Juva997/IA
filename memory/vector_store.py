try:
    import faiss  # type: ignore
except Exception:
    faiss = None

import os
import numpy as np
import threading

from utils.cache import Cache


class VectorStore:
    def __init__(self, embedding_fn, vector_size=None, max_entries=None):
        self.embedding_fn = embedding_fn
        # Determine vector size from explicit parameter, environment or default to 256
        try:
            if vector_size is not None:
                self.vector_size = int(vector_size)
            else:
                self.vector_size = int(os.environ.get("EMBEDDINGS_VECTOR_SIZE", "256"))
        except Exception:
            self.vector_size = 256
        self.texts = []
        self.metadatas = []
        self._lock = threading.RLock()

        # max entries for the in-memory store (eviction threshold)
        try:
            default_max = int(os.environ.get("VECTORSTORE_MAX_ENTRIES", "10000"))
        except Exception:
            default_max = 10000
        self.max_entries = int(max_entries) if max_entries is not None else default_max

        # Cache embeddings por 1 hora com limite de itens para evitar crescimento ilimitado
        try:
            max_items = int(os.environ.get("EMBEDDING_CACHE_MAX_ITEMS", "10000"))
        except Exception:
            max_items = 10000
        self.embedding_cache = Cache(ttl=3600, max_items=max_items)

        # Use FAISS if available, otherwise use a simple numpy-backed fallback
        if faiss is not None:
            self._use_faiss = True
            self.index = faiss.IndexFlatIP(self.vector_size)  # Inner product for cosine
        else:
            self._use_faiss = False
            self._fallback_index = []  # list of numpy vectors

    # =========================
    # ➕ ADD (com evicção LRU)
    # =========================
    def add(self, text, metadata=None):
        try:
            # compute embedding outside lock (may be expensive)
            embedding = self._safe_embed(text)
            if not embedding:
                return

            embedding_np = np.array([embedding], dtype=np.float32)

            with self._lock:
                if self._use_faiss:
                    try:
                        faiss.normalize_L2(embedding_np)  # Normalize for cosine
                        self.index.add(embedding_np)
                    except Exception:
                        # If faiss fails during add, fallback to numpy
                        self._use_faiss = False
                        emb_row = embedding_np[0]
                        norm = np.linalg.norm(emb_row)
                        if norm > 0:
                            emb_row = emb_row / norm
                        self._fallback_index.append(emb_row)
                else:
                    # normalize and store in fallback list
                    emb_row = embedding_np[0]
                    norm = np.linalg.norm(emb_row)
                    if norm > 0:
                        emb_row = emb_row / norm
                    self._fallback_index.append(emb_row)

                self.texts.append(text)
                self.metadatas.append(metadata or {})

                # Evict oldest items if exceeding max_entries (LRU by access not tracked; evict oldest)
                if self.max_entries and len(self.texts) > self.max_entries:
                    evict_count = len(self.texts) - self.max_entries

                    # Trim lists
                    remaining_texts = self.texts[evict_count:]
                    remaining_metas = self.metadatas[evict_count:]

                    # Rebuild index for faiss fallback if needed
                    if self._use_faiss:
                        try:
                            new_index = faiss.IndexFlatIP(self.vector_size)
                            emb_rows = []
                            for t in remaining_texts:
                                emb = self.embedding_cache.get(t)
                                if not emb:
                                    emb = self._safe_embed(t)
                                if not emb:
                                    continue
                                row = np.array(emb, dtype=np.float32)
                                n = np.linalg.norm(row)
                                if n > 0:
                                    row = row / n
                                emb_rows.append(row)
                            if emb_rows:
                                new_index.add(np.stack(emb_rows, axis=0))
                            self.index = new_index
                        except Exception:
                            # If rebuild fails, switch to fallback
                            self._use_faiss = False
                            # rebuild fallback index
                            self._fallback_index = []
                            for t in remaining_texts:
                                emb = self.embedding_cache.get(t) or self._safe_embed(t)
                                if not emb:
                                    continue
                                row = np.array(emb, dtype=np.float32)
                                n = np.linalg.norm(row)
                                if n > 0:
                                    row = row / n
                                self._fallback_index.append(row)
                    else:
                        # fallback list already has rows appended in same order as texts
                        self._fallback_index = self._fallback_index[evict_count:]

                    self.texts = remaining_texts
                    self.metadatas = remaining_metas

        except Exception:
            # mantém comportamento silencioso
            pass

    # =========================
    # 🔍 SEARCH
    # =========================
    def search(self, query, top_k=5):
        query_vec = self._safe_embed(query)
        if not query_vec:
            return []

        query_np = np.array([query_vec], dtype=np.float32)
        with self._lock:
            if self._use_faiss:
                try:
                    faiss.normalize_L2(query_np)
                    distances, indices = self.index.search(query_np, min(top_k, len(self.texts)))
                    results = []
                    for dist, idx in zip(distances[0], indices[0]):
                        if idx < len(self.texts):
                            results.append(
                                {
                                    "text": self.texts[idx],
                                    "metadata": self.metadatas[idx],
                                    "score": float(dist),
                                }
                            )
                    return results
                except Exception:
                    # fallback to numpy search on error
                    pass

            # Fallback search: cosine similarity via numpy
            q = query_np[0].astype(np.float32)
            qnorm = np.linalg.norm(q)
            if qnorm > 0:
                q = q / qnorm

            if not self._fallback_index:
                return []

            index_matrix = np.stack(self._fallback_index, axis=0)
            scores = index_matrix.dot(q)
            top_k = min(top_k, len(self.texts))
            order = np.argsort(-scores)[:top_k]
            results = []
            for idx in order:
                results.append({"text": self.texts[idx], "metadata": self.metadatas[idx], "score": float(scores[idx])})
            return results

    # =========================
    # 💾 SAVE/LOAD
    # =========================
    def save(self, path):
        with self._lock:
            if self._use_faiss:
                try:
                    faiss.write_index(self.index, path + ".index")
                except Exception:
                    # If faiss write fails (disk issue or incompatible index), disable faiss
                    self._use_faiss = False
            np.savez(path + ".data", texts=self.texts, metadatas=self.metadatas)

    def load(self, path):
        with self._lock:
            if self._use_faiss:
                try:
                    if os.path.exists(path + ".index"):
                        self.index = faiss.read_index(path + ".index")
                    else:
                        # index missing -> fallback to numpy approach
                        self._use_faiss = False
                except Exception:
                    # failed to read faiss index -> fallback
                    self._use_faiss = False
            data = np.load(path + ".data.npz", allow_pickle=True)
            self.texts = data["texts"].tolist()
            self.metadatas = data["metadatas"].tolist()
            # rebuild fallback index when faiss is not available
            if not self._use_faiss:
                self._fallback_index = []
                for t in self.texts:
                    try:
                        emb = self._safe_embed(t)
                        if emb:
                            emb_np = np.array(emb, dtype=np.float32)
                            norm = np.linalg.norm(emb_np)
                            if norm > 0:
                                emb_np = emb_np / norm
                            self._fallback_index.append(emb_np)
                    except Exception:
                        # ignore embedding errors during load
                        continue

    def clear(self):
        with self._lock:
            if self._use_faiss:
                try:
                    self.index = faiss.IndexFlatIP(self.vector_size)
                except Exception:
                    self._use_faiss = False
                    self._fallback_index = []
            else:
                self._fallback_index = []
            self.texts = []
            self.metadatas = []

    # =========================
    # 🔒 HELPERS
    # =========================
    def _safe_embed(self, text):
        if not text:
            return []

        cached = self.embedding_cache.get(text)
        if cached:
            return cached

        embedding = self.embedding_fn(text)

        if not isinstance(embedding, (list, tuple)):
            return []

        # Ensure correct size
        if len(embedding) != self.vector_size:
            if len(embedding) > self.vector_size:
                embedding = embedding[: self.vector_size]
            else:
                embedding += [0.0] * (self.vector_size - len(embedding))

        self.embedding_cache.set(text, embedding)
        return embedding
