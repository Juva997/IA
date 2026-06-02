from memory.vector_store import VectorStore


def simple_embedding(text, size=256):
    vec = [float(ord(c)) for c in text[:size]]
    if len(vec) < size:
        vec += [0.0] * (size - len(vec))
    return vec


def test_vector_store_add_and_search():
    store = VectorStore(simple_embedding, vector_size=256)
    store.add("Hello world")
    store.add("Goodbye world")

    results = store.search("Hello", top_k=2)
    assert len(results) == 2
    assert "Hello world" in results[0]["text"]


def test_vector_store_save_load(tmp_path):
    store = VectorStore(simple_embedding, vector_size=256)
    store.add("Test data")

    path = str(tmp_path / "test_memory")
    store.save(path)

    new_store = VectorStore(simple_embedding, vector_size=256)
    new_store.load(path)

    results = new_store.search("Test", top_k=1)
    assert len(results) == 1
    assert results[0]["text"] == "Test data"
