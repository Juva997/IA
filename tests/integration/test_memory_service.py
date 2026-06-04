def test_memory_store_and_retrieve():
    from service.memory.service import store

    # limpar estado prévio
    store.items.clear()

    store.add("hello world", {"tag": "t1"})
    results = store.retrieve("hello", top_k=5)

    assert isinstance(results, list)
    assert len(results) >= 1
    assert results[0]["text"] == "hello world"
