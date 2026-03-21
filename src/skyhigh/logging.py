import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

from skyhigh.observability.context import request_id_ctx


class JsonLogFormatter(logging.Formatter):
    """JSON lines for structured logs (timestamp, level, request_id, message)."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", request_id_ctx.get("-")),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level.upper())

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonLogFormatter())
    root.addHandler(handler)

    # Reduce noise from libraries in production-like defaults
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
