from fastapi import FastAPI, Request
from pydantic import BaseModel
from typing import Optional
import time

app = FastAPI()


class GenerateRequest(BaseModel):
    model: Optional[str] = None
    prompt: Optional[str] = None
    stream: Optional[bool] = False


@app.post("/api/generate")
async def generate(req: GenerateRequest):
    prompt = (req.prompt or "").strip()
    # Resposta simples: ecoa e adiciona info de mock
    text = f"[MOCK LLM resposta] modelo={req.model or 'mock'} prompt={prompt}"
    return {"response": text}


@app.get("/api/tags")
async def tags():
    # lista de modelos de exemplo
    models = [
        "codellama:7b",
        "deepseek-r1:1.5b",
        "deepseek-r1:8b",
        "llama3.1:8b",
        "llama3.2:3b",
        "llama3:latest",
        "mistral:latest",
        "phi3:mini",
        "qwen2.5-coder:7b",
        "qwen2.5:3b",
        "qwen3.5:4b",
    ]
    return {"models": [{"name": m} for m in models]}


@app.get("/health")
async def health():
    return {"status": "ok", "time": time.time()}
