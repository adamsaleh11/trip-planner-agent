from __future__ import annotations

import os
import random
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SpanRecord:
    name: str
    trace_id: str
    attributes: dict[str, Any] = field(default_factory=dict)


class ActiveSpan:
    def __init__(self, name: str, trace_id: str, attributes: dict[str, Any]) -> None:
        self.name = name
        self.trace_id = trace_id
        self.attributes = _safe_attributes(attributes)
        self._otel_span = _start_otel_span(name, trace_id, self.attributes)
        _recorded_spans.append(SpanRecord(name, trace_id, dict(self.attributes)))

    def end(self, error: Exception | None = None) -> None:
        if self._otel_span is None:
            return
        try:
            if error is not None:
                self._otel_span.record_exception(error)
                self._otel_span.set_attribute("error", True)
            self._otel_span.end()
        except Exception:
            return


_recorded_spans: list[SpanRecord] = []
_configured = False
_forced_trace_id: ContextVar[int | None] = ContextVar("forced_trace_id", default=None)


def configure_observability() -> None:
    global _configured
    if _configured:
        return
    _configured = True
    if not os.environ.get("GCP_PROJECT") and not os.environ.get("GOOGLE_CLOUD_PROJECT"):
        return
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except Exception:
        return
    provider = TracerProvider(id_generator=_TraceIdGenerator())
    provider.add_span_processor(BatchSpanProcessor(CloudTraceSpanExporter()))
    trace.set_tracer_provider(provider)


def start_span(
    name: str,
    trace_id: str,
    attributes: dict[str, Any] | None = None,
) -> ActiveSpan:
    return ActiveSpan(name, trace_id, attributes or {})


def get_recorded_spans() -> list[SpanRecord]:
    return list(_recorded_spans)


def reset_recorded_spans() -> None:
    _recorded_spans.clear()


def _safe_attributes(attributes: dict[str, Any]) -> dict[str, Any]:
    allowed_prefixes = (
        "trip.",
        "generation.",
        "agent.",
        "model.",
        "metrics.",
        "whim.",
        "cache.",
    )
    allowed_keys = {
        "tripId",
        "category",
        "model",
        "status",
        "traceId",
        "billingTier",
    }
    return {
        key: value
        for key, value in attributes.items()
        if key in allowed_keys or key.startswith(allowed_prefixes)
    }


def _start_otel_span(name: str, trace_id: str, attributes: dict[str, Any]):
    try:
        from opentelemetry import trace
    except Exception:
        return None
    if not trace_id or len(trace_id) != 32:
        return None
    try:
        tracer = trace.get_tracer("trip-planner-agent")
        token = _forced_trace_id.set(int(trace_id, 16))
        try:
            span = tracer.start_span(name)
        finally:
            _forced_trace_id.reset(token)
        for key, value in attributes.items():
            span.set_attribute(key, value)
        return span
    except Exception:
        return None


class _TraceIdGenerator:
    def generate_span_id(self) -> int:
        return random.getrandbits(64)

    def generate_trace_id(self) -> int:
        return _forced_trace_id.get() or random.getrandbits(128)
