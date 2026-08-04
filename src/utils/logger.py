"""
Structured logging — professional terminal output.

Format:
    2026-08-05 14:23:01  INFO     [crew.airline_crew]  crew_run_started  query='Flight AI302...'

Rules:
  - Timestamps are human-readable (not ISO with T/Z)
  - Level is left-padded to 8 chars
  - Logger name is shown in brackets, trimmed to last two segments
  - No emojis, no colours by default (set LOG_COLOR=true to enable)
  - Key=value pairs printed inline after the event name
"""
from __future__ import annotations

import logging
import os
import re
import sys

import structlog

from src.config.settings import get_settings

_CONFIGURED = False

# ── Root-level filter — suppresses noisy CrewAI/LLM provider lines ───────────

_SUPPRESS_PATTERNS = re.compile(
    r"Successfully validated tool"
    r"|OpenAI API usage"
    r"|\[Finalize\]"
    r"|todos_count="
    r"|changes detected"
    r"|Using config path"
    r"|config path:"
)


class _SuppressNoisyFilter(logging.Filter):
    """Drop log records whose message matches known noisy CrewAI internals."""

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return not bool(_SUPPRESS_PATTERNS.search(msg))


def _trim_logger_name(_, __, event_dict: dict) -> dict:
    """Shorten 'src.knowledge.db2_vector_store' → 'knowledge.db2_vector_store'."""
    name = event_dict.get("logger", "")
    parts = name.split(".")
    # Keep last two segments so the name stays identifiable but compact
    event_dict["logger"] = ".".join(parts[-2:]) if len(parts) >= 2 else name
    return event_dict


def _format_kv(_, __, event_dict: dict) -> dict:
    """
    Move all extra keys into a single 'details' string appended to the event,
    so the output reads as one clean line per log entry.
    """
    event = event_dict.pop("event", "")
    level = event_dict.pop("level", "info")
    logger = event_dict.pop("logger", "")
    timestamp = event_dict.pop("timestamp", "")

    # Build key=value pairs from remaining keys (skip internal structlog keys)
    skip = {"_record", "_from_structlog", "exc_info", "stack_info"}
    pairs = " ".join(
        f"{k}={repr(v) if isinstance(v, str) else v}"
        for k, v in event_dict.items()
        if k not in skip
    )

    line = f"{timestamp}  {level.upper():<8} [{logger}]  {event}"
    if pairs:
        line += f"  {pairs}"

    event_dict.clear()
    event_dict["_rendered"] = line
    return event_dict


def _render(_, __, event_dict: dict) -> str:
    return event_dict["_rendered"]


def configure_logging() -> None:
    """Configure structlog for the application. Call once at startup."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    settings = get_settings()
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    use_colors = os.environ.get("LOG_COLOR", "false").lower() == "true"

    if use_colors:
        processors = [
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
            _trim_logger_name,
            structlog.dev.ConsoleRenderer(colors=True),
        ]
    else:
        processors = [
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
            _trim_logger_name,
            _format_kv,
            _render,
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    # Attach suppression filter to every handler on the root logger
    _noise_filter = _SuppressNoisyFilter()
    for handler in logging.root.handlers:
        handler.addFilter(_noise_filter)

    # Silence noisy third-party named loggers
    for noisy in (
        "httpx", "httpcore", "urllib3", "requests",
        "sentence_transformers", "transformers", "torch",
        "huggingface_hub", "filelock", "h11",
        "openai", "litellm",
        "watchfiles", "watchfiles.main",
    ):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    # Suppress CrewAI's internal LLM provider INFO logs (root logger used directly)
    # and the rich agent banner output which uses the crewai logger
    logging.getLogger("crewai").setLevel(logging.WARNING)
    logging.getLogger("crewai.llms").setLevel(logging.WARNING)
    logging.getLogger("crewai.experimental").setLevel(logging.WARNING)
    logging.getLogger("crewai.utilities.config_loader").setLevel(logging.WARNING)

    _CONFIGURED = True


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a named structlog logger."""
    return structlog.get_logger(name)
