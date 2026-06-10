"""Per-request context propagated via context variables.

The logging middleware seeds ``request_id`` and a default ``uid`` of ``"anon"``
at the start of each request; the auth dependency overwrites ``uid`` once the
caller is identified. Service-layer logs read these so every log line carries
the same ``request_id`` without threading it through call signatures.
"""

from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
uid_var: ContextVar[str] = ContextVar("uid", default="anon")


def set_request_id(request_id: str) -> None:
    request_id_var.set(request_id)


def get_request_id() -> str:
    return request_id_var.get()


def set_uid(uid: str) -> None:
    uid_var.set(uid)


def get_uid() -> str:
    return uid_var.get()
