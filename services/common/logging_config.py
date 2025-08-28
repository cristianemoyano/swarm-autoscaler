import logging
import os
from typing import Optional
import sys

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

    # Get and validate LOG_LEVEL
    level_name = os.getenv("LOG_LEVEL", default_level).upper()

    # Validate that the level is valid
    valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    if level_name not in valid_levels:
        print(f"Warning: Invalid LOG_LEVEL '{level_name}'. Using default '{default_level}'. Valid levels: {', '.join(valid_levels)}", file=sys.stderr)
        level_name = default_level.upper()
    
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

    # Log the configuration that was applied
    role = os.getenv("ROLE", "app")
    logger = logging.getLogger(f"{role}.logging_config")
    logger.info(f"logging configured with level={level_name} (numeric={level})")


def get_logger(service_role: str, name: Optional[str] = None) -> logging.LoggerAdapter:
    logger_name = name or service_role
    base_logger = logging.getLogger(logger_name)
    return logging.LoggerAdapter(base_logger, extra={"role": service_role})
