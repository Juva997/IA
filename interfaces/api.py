from typing import Optional
import os
import asyncio
import time
import threading

from fastapi import Depends, FastAPI, HTTPException, Header
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from bootstrap.container import build_engine
from core.diagnostics import collect_health_details

app = FastAPI(title="Assistente Local API", version="1.0.0")

# Instrumentação OTel + Requests (se disponível) e inicialização do servidor
# de métricas Prometheus na inicialização do app.
try:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.requests import RequestsInstrumentor

    try:
        FastAPIInstrumentor.instrument_app(app)
    except Exception:
        pass

    try:
        RequestsInstrumentor().instrument()
    except Exception:
        pass
except Exception:
    # OpenTelemetry não instalado; proceed sem instrumentação automática
    pass


@app.on_event("startup")
def _start_metrics_server_on_startup():
    try:
        from monitor.metrics import Metrics

        port = int(os.environ.get("METRICS_PORT", os.environ.get("SERVER_METRICS_PORT", "8001")))
        # start_http_server called inside Metrics.start_server is non-blocking,
        # but run in a daemon thread to be safe when uvicorn manages the loop.
        def _start():
            try:
                m = Metrics()
                m.start_server(port)
            except Exception:
                pass

        t = threading.Thread(target=_start, daemon=True)
        t.start()
    except Exception:
        pass

_engine = None

# Concurrency controls for expensive `engine.run` operations
_ENGINE_RUN_CONCURRENCY = int(os.environ.get("ENGINE_RUN_CONCURRENCY", "4"))
_ENGINE_RUN_SEMAPHORE_WAIT = float(os.environ.get("ENGINE_RUN_SEMAPHORE_WAIT", "2"))
_engine_run_semaphore = asyncio.Semaphore(_ENGINE_RUN_CONCURRENCY)


def get_engine():
    global _engine
    if _engine is None:
        # Allow forcing a lightweight mock engine for local load/profiling
        try:
            use_mock = str(os.environ.get("ASSISTENTE_MOCK_ENGINE", "0")).strip().lower() in ("1", "true", "yes")
        except Exception:
            use_mock = False

        if use_mock:
            class _MockEngine:
                runtime_info = {"require_api_key": False}

                def run(self, goal):
                    # Simulate light processing and return quickly
                    return {"status": "success", "output": f"mock response for: {str(goal)[:80]}"}

            _engine = _MockEngine()
        else:
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


def _require_api_key(authorization: Optional[str] = Header(None), engine=Depends(get_engine)):
    # Preferir sinalização configurada no engine (build_engine)
    require_flag = None
    try:
        if engine is not None:
            if getattr(engine, "runtime_info", None) is not None:
                require_flag = engine.runtime_info.get("require_api_key")
            else:
                # If an engine was provided (e.g. in tests) but has no runtime_info,
                # prefer that over a global environment flag to avoid test interference.
                require_flag = False
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
    # Bounded concurrency: try to acquire the semaphore with a short timeout
    try:
        try:
            await asyncio.wait_for(_engine_run_semaphore.acquire(), timeout=_ENGINE_RUN_SEMAPHORE_WAIT)
        except asyncio.TimeoutError:
            raise HTTPException(status_code=503, detail="server_busy: too many concurrent requests")

        try:
            # Run engine.run in a threadpool to avoid blocking the async event loop
            start_ts = time.time()
            result = await run_in_threadpool(engine.run, request.goal)
            duration = time.time() - start_ts
            # Record metrics if available
            try:
                from integrations.otel import get_metrics

                _metrics = get_metrics()
            except Exception:
                _metrics = None

            if _metrics:
                try:
                    _metrics.increment_requests("query")
                    _metrics.observe_response_time("query", duration)
                except Exception:
                    pass
        finally:
            try:
                _engine_run_semaphore.release()
            except Exception:
                pass

        if isinstance(result, dict):
            return QueryResponse(
                status=result.get("status", "success"),
                output=_as_optional_string(result.get("output")),
                error=_as_optional_string(result.get("error")),
            )
        else:
            return QueryResponse(status="success", output=str(result))

    except HTTPException:
        raise
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
