from contextlib import contextmanager
from functools import lru_cache
import os
import sys

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode


_NOOP_TRACER = trace.NoOpTracerProvider().get_tracer(__name__)


@lru_cache(maxsize=1)
def _console_tracer():
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor

    provider = TracerProvider(resource=Resource({"service.name": "edge-deid-extraction"}))
    provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter(out=sys.stdout)))
    return provider.get_tracer("edge-deid.pipeline")


def _get_tracer():
    mode = os.environ.get("EDGE_DEID_TRACING", "off").strip().lower()
    if mode == "off":
        return _NOOP_TRACER
    if mode == "console":
        return _console_tracer()
    raise ValueError("EDGE_DEID_TRACING must be off or console")


def mark_failed(span, reason):
    span.set_attribute("pipeline.failure", reason)
    span.set_status(Status(StatusCode.ERROR))


@contextmanager
def trace_span(name, **attributes):
    with _get_tracer().start_as_current_span(
        name,
        attributes=attributes,
        record_exception=False,
        set_status_on_exception=False,
    ) as span:
        try:
            yield span
        except Exception:
            mark_failed(span, "stage_exception")
            raise
        else:
            if span.is_recording() and span.status.status_code == StatusCode.UNSET:
                span.set_status(Status(StatusCode.OK))