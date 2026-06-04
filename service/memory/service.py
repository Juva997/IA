"""Micro-serviço de memória (protótipo minimal usando FastAPI).

Endpoints:
 - POST /ingest  : ingere texto + metadata
 - GET  /retrieve: recupera documentos por busca simples

Este é um protótipo local para facilitar a migração para um serviço
de memória desacoplado (FAISS, Pinecone, etc.).
"""
try:
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel
except Exception:
    # FastAPI não instalado: arquivo serve como blueprint
    FastAPI = None
    BaseModel = object
    HTTPException = Exception

from typing import Any, Dict, List


class IngestRequest(BaseModel):
    text: str
    metadata: Dict[str, Any] = {}


class InMemoryStore:
    def __init__(self):
        self.items: List[Dict[str, Any]] = []

    def add(self, text: str, metadata: Dict[str, Any]):
        self.items.append({"text": text, "metadata": metadata})

    def retrieve(self, q: str, top_k: int = 5):
        qlow = q.lower()
        matches = [it for it in self.items if qlow in it.get("text", "").lower()]
        return matches[:top_k]


store = InMemoryStore()

if FastAPI:
    app = FastAPI(title="Memory Service (prototype)")


    @app.post("/ingest")
    async def ingest(req: IngestRequest):
        if not req.text:
            raise HTTPException(status_code=400, detail="text required")
        store.add(req.text, req.metadata or {})
        return {"ok": True}


    @app.get("/retrieve")
    async def retrieve(q: str, k: int = 5):
        results = store.retrieve(q, top_k=k)
        return {"items": results}


__all__ = ["store"]
