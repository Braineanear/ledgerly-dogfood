"""Structured JSON logging: one JSON object per line."""

import json
import logging
from contextvars import ContextVar
from datetime import UTC, datetime

LOGGER_NAME = "ledgerly_api"

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

EXTRA_FIELDS = ("method", "path", "status", "duration_ms")


class JsonFormatter(logging.Formatter):
    """Format each record as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created, UTC)
        payload = {
            "timestamp": timestamp.isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_var.get(),
        }
        for field in EXTRA_FIELDS:
            if hasattr(record, field):
                payload[field] = getattr(record, field)
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging() -> None:
    """Attach one JSON stderr handler to the ledgerly_api logger."""
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    ours = [h for h in logger.handlers if getattr(h, "_ledgerly_json", False)]
    for h in list(logger.handlers):
        if h not in ours[:1]:
            logger.removeHandler(h)
    if not ours:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        handler._ledgerly_json = True  # type: ignore[attr-defined]
        logger.addHandler(handler)
