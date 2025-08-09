import logging
import os

DEFAULT_LEVEL = logging.DEBUG
DEFAULT_FORMAT = '%(asctime)s - %(levelname)s - %(name)s - %(message)s'

def configure_logging() -> None:
    level_name = os.getenv('LOG_LEVEL', '')
    level = getattr(logging, level_name.upper(), DEFAULT_LEVEL) if level_name else DEFAULT_LEVEL
    logging.basicConfig(format=DEFAULT_FORMAT, level=level)

    # Reduce noise from common libraries
    logging.getLogger("urllib3").setLevel(logging.INFO)
    logging.getLogger("werkzeug").setLevel(logging.INFO)
    logging.getLogger("docker").setLevel(logging.INFO)


