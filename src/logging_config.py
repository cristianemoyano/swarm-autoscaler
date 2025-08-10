import logging
import os
import sys

DEFAULT_LEVEL = logging.DEBUG
DEFAULT_FORMAT = '%(asctime)s - %(levelname)s - %(name)s - %(message)s'

def configure_logging() -> None:
    level_name = os.getenv('LOG_LEVEL', '')
    level = getattr(logging, level_name.upper(), DEFAULT_LEVEL) if level_name else DEFAULT_LEVEL

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Add a console handler (stdout) with formatter if not already present
    if not any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers):
        console_handler = logging.StreamHandler(stream=sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(logging.Formatter(DEFAULT_FORMAT))
        root_logger.addHandler(console_handler)

    # Reduce noise from common libraries
    logging.getLogger("urllib3").setLevel(logging.INFO)
    logging.getLogger("werkzeug").setLevel(logging.INFO)
    logging.getLogger("docker").setLevel(logging.INFO)


