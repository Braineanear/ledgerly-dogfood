"""Request id middleware: read or create X-Request-Id and echo it."""

import json
import logging
import re
import time
import uuid

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from ledgerly_api.logging_config import request_id_var

HEADER_NAME = b"x-request-id"
VALID_REQUEST_ID = re.compile(r"[A-Za-z0-9._-]{1,128}")

logger = logging.getLogger("ledgerly_api")
access_logger = logging.getLogger("ledgerly_api.access")


# Use the first x-request-id header if valid, else a new uuid4 hex id.
def _incoming_request_id(scope: Scope) -> str:
    """Return the supplied id if it is valid, else a new uuid4 hex."""
    for name, value in scope.get("headers", []):
        if name.lower() == HEADER_NAME:
            candidate = value.decode("latin-1")
            if VALID_REQUEST_ID.fullmatch(candidate):
                return candidate
            break
    return uuid.uuid4().hex


class RequestIdMiddleware:
    """Pure ASGI middleware that sets, echoes and logs the request id."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _incoming_request_id(scope)
        token = request_id_var.set(request_id)
        header = (HEADER_NAME, request_id.encode("latin-1"))
        started = False
        status = 500
        start = time.perf_counter()

        async def send_with_id(message: Message) -> None:
            nonlocal started, status
            if message["type"] == "http.response.start":
                started = True
                status = message["status"]
                headers = [
                    (name, value)
                    for name, value in message.get("headers", [])
                    if name.lower() != HEADER_NAME
                ]
                headers.append(header)
                message = {**message, "headers": headers}
            await send(message)

        try:
            try:
                await self.app(scope, receive, send_with_id)
            except Exception:
                status = 500
                logger.exception("unhandled exception")
                if started:
                    raise
                payload = json.dumps({"detail": "Internal Server Error"}).encode(
                    "utf-8"
                )
                await send_with_id(
                    {
                        "type": "http.response.start",
                        "status": 500,
                        "headers": [
                            (b"content-type", b"application/json"),
                            (b"content-length", str(len(payload)).encode()),
                        ],
                    }
                )
                await send_with_id({"type": "http.response.body", "body": payload})
            finally:
                duration_ms = round((time.perf_counter() - start) * 1000, 3)
                access_logger.info(
                    "request",
                    extra={
                        "method": scope["method"],
                        "path": scope["path"],
                        "status": status,
                        "duration_ms": duration_ms,
                    },
                )
        finally:
            request_id_var.reset(token)
