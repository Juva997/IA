from typing import Optional

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel

from bootstrap.container import build_engine
from core.diagnostics import collect_health_details

app = FastAPI(title="Assistente Local API", version="1.0.0")

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = build_engine()
    return _engine


def set_engine_for_tests(engine):
    global _engine
    _engine = engine


class QueryRequest(BaseModel):
    goal: str


class QueryResponse(BaseModel):
    status: str
    output: Optional[str] = None
    error: Optional[str] = None


@app.post("/query", response_model=QueryResponse)
async def query_assistant(request: QueryRequest, engine=Depends(get_engine)):
    try:
        result = engine.run(request.goal)

        if isinstance(result, dict):
            return QueryResponse(
                status=result.get("status", "success"),
                output=_as_optional_string(result.get("output")),
                error=_as_optional_string(result.get("error")),
            )
        else:
            return QueryResponse(status="success", output=str(result))

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/query")
async def query_usage():
    return {
        "message": "Use POST /query com JSON {'goal': 'sua pergunta'}",
        "example": {"goal": "oi"},
        "docs": "/docs",
    }


@app.get("/")
async def root():
    return {
        "message": "Assistente Local API - Use POST /query com {'goal': 'sua pergunta'}"
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/health/details")
async def health_details(engine=Depends(get_engine)):
    return collect_health_details(engine)


def _as_optional_string(value):
    if value is None:
        return None
    return str(value)
