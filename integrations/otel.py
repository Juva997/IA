"""
Inicialização mínima OpenTelemetry (PoC) e helper para obter tracer/metrics.

Configura um TracerProvider com exportador OTLP se `OTEL_EXPORTER_OTLP_ENDPOINT`
estiver configurado, senão usa ConsoleSpanExporter como fallback.

Também expõe `get_metrics()` que retorna a instância `monitor.metrics.Metrics`.
"""
import os
from contextlib import suppress

try:
    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    _otel_available = True
except Exception:
    _otel_available = False

_metrics = None

if _otel_available:
    try:
        # prefer OTLP exporter when endpoint explicitamente configurado
        otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
        provider = TracerProvider(resource=Resource.create({"service.name": "ia-service"}))
        trace.set_tracer_provider(provider)

        if otlp_endpoint:
            with suppress(Exception):
                try:
                    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

                    exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
                except Exception:
                    exporter = ConsoleSpanExporter()
        else:
            exporter = ConsoleSpanExporter()

        provider.add_span_processor(BatchSpanProcessor(exporter))
    except Exception:
        # continue silently on init failures
        _otel_available = False


def get_tracer(name: str = "ia"):
    if not _otel_available:
        class _Noop:
            def start_as_current_span(self, *a, **kw):
                from contextlib import nullcontext

                return nullcontext()

        return _Noop()

    from opentelemetry import trace as _trace

    return _trace.get_tracer(name)


def get_metrics():
    global _metrics
    if _metrics is not None:
        return _metrics

    try:
        from monitor.metrics import Metrics

        _metrics = Metrics()
    except Exception:
        _metrics = None
    return _metrics
