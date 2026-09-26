"""Request-ID propagation, request logging and HTTP metrics.

Pure ASGI middleware (not BaseHTTPMiddleware) so the ContextVar we set is visible
inside route handlers and survives the thread-pool hop of sync endpoints.
"""

import logging
import time
import uuid

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.logging_config import request_id_var
from app.metrics import REQUEST_COUNT, REQUEST_LATENCY

logger = logging.getLogger("civicpulse.http")


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
        request_id = headers.get("x-request-id") or uuid.uuid4().hex
        token = request_id_var.set(request_id)
        start = time.perf_counter()
        status_code = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                raw_headers = list(message.get("headers", []))
                raw_headers.append((b"x-request-id", request_id.encode()))
                message["headers"] = raw_headers
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            elapsed = time.perf_counter() - start
            # Use the route template (/api/complaints/{complaint_id}) not the raw path,
            # otherwise every UUID becomes a new metric label and Prometheus explodes.
            route = scope.get("route")
            path = getattr(route, "path", None) or "unmatched"
            method = scope.get("method", "GET")
            REQUEST_COUNT.labels(method, path, str(status_code)).inc()
            REQUEST_LATENCY.labels(method, path).observe(elapsed)
            if path not in ("/health", "/ready", "/metrics"):
                logger.info(
                    "request",
                    extra={
                        "method": method,
                        "path": scope.get("path"),
                        "status": status_code,
                        "duration_ms": round(elapsed * 1000, 1),
                    },
                )
            request_id_var.reset(token)
