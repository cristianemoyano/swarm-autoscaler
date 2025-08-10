from flask import Flask
from autoscaler_service import AutoscalerService
from docker_service import DockerService
from discovery import Discovery
from cache import Cache
import os
import logging
from settings import MIN_PERCENTAGE, MAX_PERCENTAGE, DISCOVERY_DNSNAME, CHECK_INTERVAL, DRY_RUN
from logging_config import configure_logging

# Configuration is now loaded from settings.py

# Configure Logging
configure_logging()

# Initialize
App = Flask(__name__)
MemoryCache = Cache()
SwarmService = DockerService(MemoryCache, DRY_RUN)
DiscoveryService = Discovery(DISCOVERY_DNSNAME, MemoryCache, CHECK_INTERVAL)

# Import routes
from urls import *

def _start_autoscaler_thread():
    autoscalerService = AutoscalerService(SwarmService, DiscoveryService, CHECK_INTERVAL, MIN_PERCENTAGE, MAX_PERCENTAGE)
    autoscalerService.daemon = True
    autoscalerService.start()

# Start autoscaler when the first worker process loads the app
if os.getenv("GUNICORN_WORKER_ID", "1") == "1":
    try:
        _start_autoscaler_thread()
    except Exception:
        logging.getLogger("main").exception("Failed to start autoscaler thread")

if __name__ == "__main__":
    _start_autoscaler_thread()
    App.run(host='0.0.0.0', port=80)
