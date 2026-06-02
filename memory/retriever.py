class Retriever:
    def __init__(self, vector_store):
        self.vector_store = vector_store

    # =========================
    def retrieve(self, query, top_k=5):
        if not query:
            return []

        try:
            results = self.vector_store.search(query, top_k)
            texts = self._extract_texts(results)

            # 🔥 fallback simples (se vector falhar)
            if not texts and hasattr(self.vector_store, "vectors"):
                return self._fallback_search(query)

            return texts

        except Exception:
            return []

    # =========================
    def _extract_texts(self, results):
        texts = []

        for r in results:
            if isinstance(r, dict):
                text = r.get("text")
                if text:
                    texts.append(text)

        return texts

    # =========================
    # 🔥 fallback semântico simples
    # =========================
    def _fallback_search(self, query):
        query = query.lower()
        results = []

        for v in getattr(self.vector_store, "vectors", []):
            if query in str(v).lower():
                results.append(v)

        return results[:5]
