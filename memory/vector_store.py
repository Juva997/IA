try:
    import faiss  # type: ignore
except Exception:
    faiss = None

import numpy as np

from utils.cache import Cache


class VectorStore:
    def __init__(self, embedding_fn, vector_size=384):
        self.embedding_fn = embedding_fn
        self.vector_size = vector_size
        self.texts = []
        self.metadatas = []
        self.embedding_cache = Cache(ttl=3600)  # Cache embeddings por 1 hora

        # Use FAISS if available, otherwise use a simple numpy-backed fallback
        if faiss is not None:
            self._use_faiss = True
            self.index = faiss.IndexFlatIP(vector_size)  # Inner product for cosine
        else:
            self._use_faiss = False
            self._fallback_index = []  # list of numpy vectors

    # =========================
    # ➕ ADD
    # =========================
    def add(self, text, metadata=None):
        try:
            embedding = self._safe_embed(text)
            if embedding:
                embedding_np = np.array([embedding], dtype=np.float32)
                if self._use_faiss:
                    faiss.normalize_L2(embedding_np)  # Normalize for cosine
                    self.index.add(embedding_np)
                else:
                    # normalize and store in fallback list
                    norm = np.linalg.norm(embedding_np)
                    if norm > 0:
                        embedding_np = embedding_np / norm
                    self._fallback_index.append(embedding_np[0])

                self.texts.append(text)
                self.metadatas.append(metadata or {})

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
        if self._use_faiss:
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
        if self._use_faiss:
            faiss.write_index(self.index, path + ".index")
        np.savez(path + ".data", texts=self.texts, metadatas=self.metadatas)

    def load(self, path):
        if self._use_faiss:
            self.index = faiss.read_index(path + ".index")
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
        if self._use_faiss:
            self.index = faiss.IndexFlatIP(self.vector_size)
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
