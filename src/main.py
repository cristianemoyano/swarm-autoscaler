from flask import Flask
from autoscaler_service import AutoscalerService
from docker_service import DockerService
from discovery import Discovery
from cache import Cache
import os
import logging
import fcntl
import atexit
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

_AUTOSCALER_LOCK_FD = None

def _acquire_singleton_lock():
    """Ensure only one Gunicorn worker starts the autoscaler in this container.
    Uses an advisory file lock that is released automatically when the process exits.
    """
    path = os.getenv("AUTOSCALER_LOCK_FILE", "/tmp/swarm-autoscaler.lock")
    try:
        fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o644)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fd
    except BlockingIOError:
        try:
            os.close(fd)  # type: ignore[name-defined]
        except Exception:
            pass
        return None
    except Exception:
        # If lock mechanism fails, fall back to single-worker guard only
        return None

def _release_singleton_lock():
    """Release the autoscaler singleton lock at process exit."""
    global _AUTOSCALER_LOCK_FD
    try:
        if _AUTOSCALER_LOCK_FD is not None:
            try:
                fcntl.flock(_AUTOSCALER_LOCK_FD, fcntl.LOCK_UN)
            except Exception:
                pass
            try:
                os.close(_AUTOSCALER_LOCK_FD)
            except Exception:
                pass
            _AUTOSCALER_LOCK_FD = None
    except Exception:
        pass

atexit.register(_release_singleton_lock)

def _start_autoscaler_thread():
    autoscalerService = AutoscalerService(SwarmService, DiscoveryService, CHECK_INTERVAL, MIN_PERCENTAGE, MAX_PERCENTAGE)
    autoscalerService.daemon = True
    autoscalerService.start()

# Start autoscaler once per container using a file-lock singleton.
# This runs for any server (Gunicorn or Flask dev), independent of env vars.
lock_fd = _acquire_singleton_lock()
if lock_fd is not None:
    _AUTOSCALER_LOCK_FD = lock_fd
    try:
        _start_autoscaler_thread()
        wid = os.getenv("GUNICORN_WORKER_ID", "-")
        logging.getLogger("main").info("Autoscaler started (worker=%s, singleton lock acquired)", wid)
    except Exception:
        logging.getLogger("main").exception("Failed to start autoscaler thread")

if __name__ == "__main__":
    # When running directly (not under Gunicorn), still enforce a lock to avoid duplicates
    fd = _acquire_singleton_lock()
    if fd is not None:
        _AUTOSCALER_LOCK_FD = fd
        _start_autoscaler_thread()
    else:
        logging.getLogger("main").info("Autoscaler not started (lock held by another process)")
    App.run(host='0.0.0.0', port=80)
