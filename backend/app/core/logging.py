"""Structured JSON logging (§19 observability).

One line of JSON per event so logs are queryable in any aggregator (CloudWatch,
Loki, Datadog). Correlate pipeline events by `job_id` (the pipeline already logs
it). Call `setup_logging()` once at process start.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        # include any structured extras passed via logger.x(..., extra={...})
        for k, v in record.__dict__.items():
            if k not in _STD and not k.startswith("_"):
                payload[k] = v
        return json.dumps(payload, default=str)


_STD = set(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {"taskName"}


def setup_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    # quiet noisy libs
    for noisy in ("uvicorn.access", "sqlalchemy.engine"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
