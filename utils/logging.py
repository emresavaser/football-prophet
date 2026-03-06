"""Structured logging setup with structlog."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

try:
    import structlog
except ImportError:  # pragma: no cover - fallback for lightweight environments
    structlog = None


def setup_logging(
    level: str = "INFO",
    log_dir: Optional[Path] = None,
    json_output: bool = False,
) -> None:
    """Configure structlog + stdlib logging."""
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Stdlib logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    # File handler
    if log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_dir / "football_prophet.log", encoding="utf-8")
        fh.setLevel(log_level)
        fh.setFormatter(logging.Formatter("%(message)s"))
        logging.getLogger().addHandler(fh)

    if structlog is None:
        return

    # Structlog processors
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if json_output:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=sys.stdout.isatty()))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str):
    """Get a structured logger when available, otherwise stdlib logger."""
    if structlog is None:
        return logging.getLogger(name)
    return structlog.get_logger(name)
