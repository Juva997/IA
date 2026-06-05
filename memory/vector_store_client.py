"""
Factory para criar um VectorStore compatível com o código atual.

Uso:
  from memory.vector_store_client import create_vector_store
  store = create_vector_store(embedding_fn, driver="qdrant", url="http://...", collection="mem")

Se o driver não estiver disponível, retorna a implementação local `memory.vector_store.VectorStore`.
"""
import os
from typing import Any, Optional


def _get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    try:
        return os.environ.get(name, default)
    except Exception:
        return default


def create_vector_store(embedding_fn, driver: Optional[str] = None, **kwargs) -> Any:
    """Cria um client para vector DB conforme `driver`.

    driver: 'qdrant' | 'milvus' | 'local' | None (fallback to env VECTORDB_DRIVER)
    kwargs: url/host/port/collection/vector_size
    """
    drv = (driver or _get_env("VECTORDB_DRIVER") or "").strip().lower()
    if not drv:
        drv = "local"

    if drv == "qdrant":
        try:
            from .vector_store_qdrant import QdrantVectorStoreAdapter

            url = kwargs.get("url") or _get_env("QDRANT_URL") or _get_env("VECTORDB_URL")
            collection = kwargs.get("collection") or _get_env("VECTORDB_COLLECTION") or "default"
            vector_size = kwargs.get("vector_size") or int(_get_env("EMBEDDINGS_VECTOR_SIZE") or 256)
            return QdrantVectorStoreAdapter(embedding_fn=embedding_fn, url=url, collection=collection, vector_size=vector_size)
        except Exception as e:
            # fallback to local
            pass

    if drv == "milvus":
        try:
            from .vector_store_milvus import MilvusVectorStoreAdapter

            host = kwargs.get("host") or _get_env("MILVUS_HOST") or _get_env("VECTORDB_HOST")
            port = kwargs.get("port") or int(_get_env("MILVUS_PORT") or 19530)
            collection = kwargs.get("collection") or _get_env("VECTORDB_COLLECTION") or "default"
            vector_size = kwargs.get("vector_size") or int(_get_env("EMBEDDINGS_VECTOR_SIZE") or 256)
            return MilvusVectorStoreAdapter(embedding_fn=embedding_fn, host=host, port=port, collection=collection, vector_size=vector_size)
        except Exception:
            # fallback
            pass

    # fallback to local VectorStore
    try:
        from .vector_store import VectorStore

        vector_size = kwargs.get("vector_size") or int(_get_env("EMBEDDINGS_VECTOR_SIZE") or 256)
        return VectorStore(embedding_fn, vector_size=vector_size)
    except Exception as e:
        raise RuntimeError("No vector store implementation available: %s" % e)
