from importlib import reload

import memory.vector_store as vs_mod


def make_embedding(vector_size):
    def fn(text: str):
        base = ord(text[0]) if text else 0
        return [((base + i) % 10) / 10.0 for i in range(vector_size)]

    return fn


def test_vectorstore_eviction_basic():
    # Force fallback (no faiss) to make test deterministic
    vs_mod.faiss = None
    reload(vs_mod)

    from memory.vector_store import VectorStore

    vs = VectorStore(make_embedding(4), vector_size=4, max_entries=3)
    vs.clear()

    vs.add("a")
    vs.add("b")
    vs.add("c")
    assert len(vs.texts) == 3
    assert vs.texts == ["a", "b", "c"]

    # Adding a new item should evict the oldest ("a")
    vs.add("d")
    assert len(vs.texts) == 3
    assert vs.texts == ["b", "c", "d"]

    # Search should find the recently added item
    results = vs.search("d", top_k=1)
    assert results and results[0]["text"] == "d"
