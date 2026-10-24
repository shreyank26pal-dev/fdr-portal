"""Request-scoped context (client IP) so services can audit without passing Request around."""
from contextvars import ContextVar

request_ip: ContextVar[str | None] = ContextVar("request_ip", default=None)
