"""Structured JSON logging and the request-logging middleware.

Every log line is a single JSON object carrying the active ``request_id`` (and
``uid`` where known). The middleware assigns a ``request_id`` per request,
records latency, and logs method/path/status/latency_ms/uid once the response
is ready.
"""

from __future__ import annotations

import json
import logging
import sys
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.context import get_request_id, set_request_id

access_logger = logging.getLogger("app.access")

# Standard LogRecord attributes; anything else on a record is a caller "extra".
_RESERVED = set(
    logging.makeLogRecord({}).__dict__.keys()
) | {"message", "asctime", "taskName"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": get_request_id(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED:
                payload[key] = value
        return json.dumps(payload, default=str)


class _StdoutHandler(logging.StreamHandler):
    """Stream handler that resolves ``sys.stdout`` lazily on each emit.

    Binding the stream at construction time would pin it to whatever object
    ``sys.stdout`` was then, ignoring later redirection. Resolving it per-emit
    keeps logs following the current stdout.
    """

    @property
    def stream(self):
        return sys.stdout

    @stream.setter
    def stream(self, _value):
        pass


def configure_logging(level: int = logging.INFO) -> None:
    """Install a single stdout JSON handler on the root logger (idempotent)."""
    handler = _StdoutHandler()
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.setLevel(level)
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = uuid.uuid4().hex
        set_request_id(request_id)
        request.state.request_id = request_id
        request.state.uid = "anon"

        start = time.perf_counter()
        response = await call_next(request)
        latency_ms = round((time.perf_counter() - start) * 1000, 2)

        access_logger.info(
            "request",
            extra={
                "request_id": request_id,
                "uid": getattr(request.state, "uid", "anon"),
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "latency_ms": latency_ms,
            },
        )
        response.headers["X-Request-ID"] = request_id
        return response
