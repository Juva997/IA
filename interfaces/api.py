from typing import Optional
import os

from fastapi import Depends, FastAPI, HTTPException, Header
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


def _require_api_key(authorization: Optional[str] = Header(None)):
    # Preferir sinalização configurada no engine (build_engine)
    try:
        engine = get_engine()
    except Exception:
        engine = None

    require_flag = None
    try:
        if engine and getattr(engine, "runtime_info", None) is not None:
            require_flag = engine.runtime_info.get("require_api_key")
    except Exception:
        require_flag = None

    if require_flag is None:
        require_flag = os.environ.get("ASSISTENTE_REQUIRE_API_KEY", "0").strip().lower() in (
            "1",
            "true",
            "yes",
        )

    if not require_flag:
        return True

    api_key = os.environ.get("ASSISTENTE_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=500, detail="server_misconfigured: ASSISTENTE_API_KEY not set")
    if not authorization:
        raise HTTPException(status_code=401, detail="missing_authorization")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="invalid_authorization_scheme")
    token = authorization.split(" ", 1)[1].strip()
    if token != api_key:
        raise HTTPException(status_code=403, detail="invalid_api_key")
    return True


@app.post("/query", response_model=QueryResponse)
async def query_assistant(request: QueryRequest, auth=Depends(_require_api_key), engine=Depends(get_engine)):
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
