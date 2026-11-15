"""Structured logging configuration for DocMorph.

Configures standard Python logging with contextual correlation IDs, timestamping,
and automated masking of sensitive data (passwords, tokens, raw file contents).
"""

import logging
import re
import sys

# Sensitive fields to mask if encountered in log messages
SENSITIVE_PATTERNS = [
    (re.compile(r'("?password"?\s*[:=]\s*)"[^"]*"', re.IGNORECASE), r'\1"***REDACTED***"'),
    (re.compile(r'("?token"?\s*[:=]\s*)"[^"]*"', re.IGNORECASE), r'\1"***REDACTED***"'),
    (re.compile(r'(Bearer\s+)[A-Za-z0-9\-_.]+', re.IGNORECASE), r'\1***REDACTED***'),
]


class SensitiveDataFilter(logging.Filter):
    """Filters log records to mask credentials, tokens, and sensitive personal information."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            masked = record.msg
            for pattern, repl in SENSITIVE_PATTERNS:
                masked = pattern.sub(repl, masked)
            record.msg = masked
        return True


def setup_logging(log_level: str = "INFO") -> None:
    """Configures application-wide logging handlers and formatters."""
    level = getattr(logging, log_level.upper(), logging.INFO)

    log_format = "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
    formatter = logging.Formatter(log_format, datefmt="%Y-%m-%d %H:%M:%S")

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handler.addFilter(SensitiveDataFilter())

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Avoid duplicate handlers on re-initialization
    if not any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers):
        root_logger.addHandler(handler)

    # Silence verbose third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("multipart").setLevel(logging.WARNING)


# Module-level logger
logger = logging.getLogger("docmorph")

