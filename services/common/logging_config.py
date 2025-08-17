import logging
import os
from typing import Optional

_is_configured = False


class RoleInjectingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:  # type: ignore[override]
        # Ensure 'role' is always present to avoid KeyError in format
        if not hasattr(record, "role"):
            setattr(record, "role", os.getenv("ROLE", "app"))
        return super().format(record)


def configure_logging(default_level: str = "INFO") -> None:
    global _is_configured
    if _is_configured:
        return

    level_name = os.getenv("LOG_LEVEL", default_level).upper()
    level = getattr(logging, level_name, logging.INFO)

    root = logging.getLogger()
    root.setLevel(level)

    handler = logging.StreamHandler()
    fmt = os.getenv(
        "LOG_FORMAT",
        "%(asctime)s %(levelname)s role=%(role)s logger=%(name)s %(message)s",
    )
    datefmt = os.getenv("LOG_DATEFMT", "%Y-%m-%dT%H:%M:%S%z")
    handler.setFormatter(RoleInjectingFormatter(fmt=fmt, datefmt=datefmt))

    root.handlers[:] = [handler]

    # Quiet third-party loggers unless explicitly overridden
    for noisy in ("urllib3", "docker", "requests"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _is_configured = True


def get_logger(service_role: str, name: Optional[str] = None) -> logging.LoggerAdapter:
    logger_name = name or service_role
    base_logger = logging.getLogger(logger_name)
    return logging.LoggerAdapter(base_logger, extra={"role": service_role})
